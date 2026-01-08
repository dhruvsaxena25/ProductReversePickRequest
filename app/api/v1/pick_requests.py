"""
==============================================================================
Pick Request Endpoints
==============================================================================

CRUD operations and picking workflow for pick requests.

==============================================================================
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, RequestStatus, RequestPriority
from app.core.dependencies import (
    get_current_user,
    require_requester,
    require_picker,
    require_admin,
)
from app.services.pick_request_service import PickRequestService
from app.services.cleanup_service import CleanupService
from app.schemas.pick_request import (
    PickRequestCreate,
    PickRequestResponse,
    PickRequestListResponse,
    PickRequestDetail,
    PickRequestBrief,
    ItemQuantityUpdate,
    ItemShortageUpdate,
    PickRequestItemResponse,
    NameValidationResponse,
    ShortageSummary,
)
from app.schemas.common import MessageResponse


router = APIRouter(prefix="/pick-requests", tags=["Pick Requests"])


class PickRequestController:
    """Controller for pick request operations."""
    
    def __init__(self, db: Session):
        self._service = PickRequestService(db)
        self._cleanup = CleanupService(db)
    
    def validate_name(self, name: str) -> NameValidationResponse:
        """Validate request name."""
        available, normalized, error = self._service.validate_name(name)
        return NameValidationResponse(
            available=available,
            normalized_name=normalized,
            error=error
        )
    
    def create(self, data: PickRequestCreate, user: User) -> PickRequestResponse:
        """Create pick request."""
        request = self._service.create_request(data, user)
        return PickRequestResponse(request=PickRequestDetail.from_model(request))
    
    def list_all(
        self,
        status: Optional[RequestStatus],
        priority: Optional[RequestPriority],
        user: User,
        mine: bool,
        offset: int,
        limit: int
    ) -> PickRequestListResponse:
        """List pick requests with filters, sorted by priority."""
        created_by = user.id if mine else None
        requests = self._service.list_requests(
            status=status,
            created_by=created_by,
            priority=priority,
            offset=offset,
            limit=limit
        )
        total = self._service.count_requests(
            status=status, 
            created_by=created_by,
            priority=priority
        )
        
        return PickRequestListResponse(
            requests=[PickRequestBrief.from_model(r) for r in requests],
            total=total
        )
    
    def get(self, name: str) -> PickRequestResponse:
        """Get pick request by name."""
        request = self._service.get_by_name(name)
        return PickRequestResponse(request=PickRequestDetail.from_model(request))
    
    def delete(self, name: str, user: User) -> MessageResponse:
        """Delete pick request."""
        self._service.delete_request(name, user)
        return MessageResponse(message=f"Pick request '{name}' deleted")
    
    def start(self, name: str, user: User) -> dict:
        """Start picking."""
        request = self._service.start_picking(name, user)
        return {
            "success": True,
            "message": "Pick request started",
            "request": PickRequestDetail.from_model(request)
        }
    
    def update_item(
        self,
        name: str,
        upc: str,
        update: ItemQuantityUpdate,
        user: User
    ) -> dict:
        """Update item quantity."""
        item = self._service.update_item_quantity(name, upc, update, user)
        return {
            "success": True,
            "item": PickRequestItemResponse.from_model(item).model_dump()
        }
    
    def submit(self, name: str, user: User, validate_shortages: bool = True) -> dict:
        """Submit completed request."""
        request, log_file = self._service.submit_request(
            name, user, validate_shortages=validate_shortages
        )
        
        status_msg = "partially completed" if request.has_shortages else "completed"
        
        return {
            "success": True,
            "message": f"Pick request {status_msg}",
            "request": PickRequestDetail.from_model(request),
            "log_file": log_file,
            "has_shortages": request.has_shortages
        }
    
    def set_shortage(
        self,
        name: str,
        upc: str,
        update: ItemShortageUpdate,
        user: User
    ) -> dict:
        """Set shortage reason for an item."""
        item = self._service.set_item_shortage(name, upc, update, user)
        return {
            "success": True,
            "item": PickRequestItemResponse.from_model(item).model_dump()
        }
    
    def get_shortages(self, name: str) -> dict:
        """Get shortage summary for a request."""
        request = self._service.get_by_name(name)
        summary = ShortageSummary.from_request(request)
        return {
            "success": True,
            "request_name": name,
            "summary": summary.model_dump()
        }
    
    def release(self, name: str, user: User) -> PickRequestResponse:
        """Release lock."""
        request = self._service.release_lock(name, user)
        return PickRequestResponse(request=PickRequestDetail.from_model(request))
    
    def resume(self, name: str, user: User) -> dict:
        """Resume picking a paused or partially completed request."""
        request = self._service.resume_picking(name, user)
        return {
            "success": True,
            "message": "Pick request resumed",
            "request": PickRequestDetail.from_model(request)
        }
    
    def pause(self, name: str, user: User) -> dict:
        """Pause picking (keep lock)."""
        request = self._service.pause_picking(name, user)
        return {
            "success": True,
            "message": "Pick request paused",
            "request": PickRequestDetail.from_model(request)
        }
    
    def cancel(self, name: str, user: User) -> dict:
        """Cancel the request."""
        request = self._service.cancel_request(name, user)
        return {
            "success": True,
            "message": "Pick request cancelled",
            "request": PickRequestDetail.from_model(request)
        }
    
    def approve(self, name: str, user: User, notes: Optional[str] = None) -> dict:
        """Approve partially completed request as complete."""
        request = self._service.approve_request(name, user, notes)
        return {
            "success": True,
            "message": "Pick request approved and completed",
            "request": PickRequestDetail.from_model(request)
        }


# ==== NAME VALIDATION ====

@router.get("/validate-name/{name}", response_model=NameValidationResponse)
async def validate_request_name(
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate if a request name is available."""
    controller = PickRequestController(db)
    return controller.validate_name(name)


# ==== CRUD ====

@router.post("", response_model=PickRequestResponse)
async def create_pick_request(
    request: PickRequestCreate,
    user: User = Depends(require_requester),
    db: Session = Depends(get_db)
):
    """Create a new pick request (Requester/Admin only)."""
    controller = PickRequestController(db)
    return controller.create(request, user)


@router.get("", response_model=PickRequestListResponse)
async def list_pick_requests(
    status: Optional[RequestStatus] = Query(None),
    priority: Optional[RequestPriority] = Query(None),
    mine: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List pick requests with optional filters.
    
    Results are sorted by priority (urgent first), then by creation date.
    """
    controller = PickRequestController(db)
    return controller.list_all(status, priority, user, mine, offset, limit)


@router.get("/{name}", response_model=PickRequestResponse)
async def get_pick_request(
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pick request by name."""
    controller = PickRequestController(db)
    return controller.get(name)


@router.delete("/{name}", response_model=MessageResponse)
async def delete_pick_request(
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a pick request (Owner/Admin only)."""
    controller = PickRequestController(db)
    return controller.delete(name, user)


# ==== PICKING WORKFLOW ====

@router.post("/{name}/start")
async def start_picking(
    name: str,
    user: User = Depends(require_picker),
    db: Session = Depends(get_db)
):
    """Start picking a request (Picker/Admin only)."""
    controller = PickRequestController(db)
    return controller.start(name, user)


@router.put("/{name}/items/{upc}")
async def update_item_quantity(
    name: str,
    upc: str,
    update: ItemQuantityUpdate,
    user: User = Depends(require_picker),
    db: Session = Depends(get_db)
):
    """Update picked quantity for an item (Picker/Admin only)."""
    controller = PickRequestController(db)
    return controller.update_item(name, upc, update, user)


@router.put("/{name}/items/{upc}/shortage")
async def set_item_shortage(
    name: str,
    upc: str,
    update: ItemShortageUpdate,
    user: User = Depends(require_picker),
    db: Session = Depends(get_db)
):
    """
    Set shortage reason for an item (Picker/Admin only).
    
    Call this when an item cannot be fully picked.
    Required before submitting if there are shortages.
    """
    controller = PickRequestController(db)
    return controller.set_shortage(name, upc, update, user)


@router.get("/{name}/shortages")
async def get_shortage_summary(
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get shortage summary for a request."""
    controller = PickRequestController(db)
    return controller.get_shortages(name)


@router.post("/{name}/submit")
async def submit_pick_request(
    name: str,
    skip_shortage_validation: bool = Query(False),
    user: User = Depends(require_picker),
    db: Session = Depends(get_db)
):
    """
    Submit/complete a pick request (Picker/Admin only).
    
    If there are shortages, shortage reasons must be set for all short items
    unless skip_shortage_validation=true.
    
    Returns COMPLETED or PARTIALLY_COMPLETED status based on shortages.
    """
    controller = PickRequestController(db)
    return controller.submit(name, user, validate_shortages=not skip_shortage_validation)


@router.post("/{name}/release", response_model=PickRequestResponse)
async def release_lock(
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Release lock and return request to pending.
    
    Can be called from: in_progress, paused, or partially_completed.
    Progress (picked quantities) is preserved.
    """
    controller = PickRequestController(db)
    return controller.release(name, user)


@router.post("/{name}/resume")
async def resume_picking(
    name: str,
    user: User = Depends(require_picker),
    db: Session = Depends(get_db)
):
    """
    Resume picking a paused or partially completed request (Picker/Admin only).
    
    - From PAUSED: same picker must resume (or admin)
    - From PARTIALLY_COMPLETED: any picker can pick it up
    """
    controller = PickRequestController(db)
    return controller.resume(name, user)


@router.post("/{name}/pause")
async def pause_picking(
    name: str,
    user: User = Depends(require_picker),
    db: Session = Depends(get_db)
):
    """
    Pause picking a request (Picker/Admin only).
    
    Lock is retained - only same picker can resume.
    Use this for breaks, will resume later.
    """
    controller = PickRequestController(db)
    return controller.pause(name, user)


@router.post("/{name}/cancel")
async def cancel_request(
    name: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a pick request (Creator/Admin only).
    
    Can cancel from: pending, in_progress, paused, or partially_completed.
    Cannot cancel completed or already cancelled requests.
    """
    controller = PickRequestController(db)
    return controller.cancel(name, user)


@router.post("/{name}/approve")
async def approve_request(
    name: str,
    notes: Optional[str] = Query(None, description="Approval notes"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve a partially completed request as complete (Creator/Admin only).
    
    Use this to accept a request with shortages as-is.
    Moves status from PARTIALLY_COMPLETED to COMPLETED.
    """
    controller = PickRequestController(db)
    return controller.approve(name, user, notes)


# ==== CLEANUP (Admin Only) ====

@router.delete("/cleanup/completed")
async def cleanup_completed(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete all completed requests (Admin only)."""
    service = CleanupService(db)
    count = service.cleanup_completed()
    return {"success": True, "message": f"Deleted {count} completed requests", "deleted_count": count}


@router.post("/cleanup/release-stale")
async def release_stale_locks(
    timeout_minutes: Optional[int] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Release stale locks (Admin only)."""
    service = CleanupService(db)
    released = service.release_stale_locks(timeout_minutes)
    return {"success": True, "message": f"Released {len(released)} stale locks", "released": released}


@router.get("/cleanup/stats")
async def get_cleanup_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get cleanup statistics (Admin only)."""
    service = CleanupService(db)
    return {"success": True, "stats": service.get_stats()}

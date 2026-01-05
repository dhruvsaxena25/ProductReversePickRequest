"""
==============================================================================
Health Check Endpoints
==============================================================================

System health status endpoints for monitoring and orchestration.

==============================================================================
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.catalog.catalog import get_catalog


router = APIRouter(prefix="/health", tags=["Health"])


class HealthController:
    """Controller for health check operations."""
    
    def __init__(self, db: Session):
        self._db = db
    
    def check_database(self) -> str:
        """Check database connectivity."""
        try:
            self._db.execute(text("SELECT 1"))
            return "healthy"
        except Exception:
            return "unhealthy"
    
    def check_catalog(self) -> dict:
        """Check catalog status."""
        catalog = get_catalog()
        if catalog:
            return {"status": "healthy", "products": len(catalog.products)}
        return {"status": "not_loaded", "products": 0}
    
    def get_health(self) -> dict:
        """Get full health status."""
        db_status = self.check_database()
        catalog_info = self.check_catalog()
        
        overall = "healthy" if db_status == "healthy" else "degraded"
        
        return {
            "status": overall,
            "components": {
                "api": "healthy",
                "database": db_status,
                "catalog": catalog_info["status"]
            },
            "details": {
                "products_loaded": catalog_info["products"]
            }
        }


@router.get("")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint.
    
    Returns system status including API, database, and catalog.
    """
    controller = HealthController(db)
    return controller.get_health()


@router.get("/ready")
async def readiness_check():
    """Readiness probe for container orchestration."""
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """Liveness probe for container orchestration."""
    return {"alive": True}

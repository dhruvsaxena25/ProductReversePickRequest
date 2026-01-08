"""
==============================================================================
Barcode Scanner & Warehouse Pick System - Application Entry Point
==============================================================================

Production-grade FastAPI application with:
- RESTful API endpoints
- WebSocket real-time scanning
- JWT authentication
- Background cleanup tasks

Usage:
------
    # Development
    uvicorn app.main:app --reload
    
    # Production
    uvicorn app.main:app --host 0.0.0.0 --port 8000

==============================================================================
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db import init_db
from app.api.router import api_router
from app.websockets import scanner_router, picker_router, requester_router
from app.catalog.catalog import init_catalog
from app.services.cleanup_service import CleanupTaskManager


# ============================================================================
# LOGGING SETUP
# ============================================================================

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


# ============================================================================
# APPLICATION FACTORY
# ============================================================================

class Application:
    """
    FastAPI application factory and manager.
    
    Handles application lifecycle including:
    - Startup and shutdown events
    - Middleware configuration
    - Router registration
    - Exception handler setup
    """
    
    def __init__(self):
        """Initialize the application."""
        self._settings = get_settings()
        self._cleanup_manager = CleanupTaskManager()
        self._app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title=self._settings.app_name,
            version="1.0.0",
            description="Real-time barcode detection and warehouse picking system",
            lifespan=self._lifespan,
            docs_url="/docs",
            redoc_url="/redoc",
        )
        
        # Configure middleware
        self._configure_middleware(app)
        
        # Register exception handlers
        register_exception_handlers(app)
        
        # Register routers
        self._register_routers(app)
        
        # Mount static files directory
        app.mount("/static", StaticFiles(directory="static"), name="static")
        
        # Register root endpoint
        self._register_root(app)
        
        return app
    
    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Application lifespan manager."""
        # Startup
        self._startup()
        yield
        # Shutdown
        self._shutdown()
    
    def _startup(self) -> None:
        """Application startup tasks."""
        logger.info("=" * 60)
        logger.info(f"🚀 Starting {self._settings.app_name}")
        logger.info("=" * 60)
        
        # Initialize database
        init_db()
        
        # Load product catalog
        self._load_catalog()
        
        # Start cleanup task
        if self._settings.auto_cleanup_enabled:
            self._cleanup_manager.start()
        
        logger.info("=" * 60)
        logger.info(f"✅ {self._settings.app_name} ready")
        logger.info(f"📍 Running on http://{self._settings.host}:{self._settings.port}")
        logger.info(f"🌐 Frontend: http://{self._settings.host}:{self._settings.port}/static/pages/index.html")
        logger.info(f"📖 API Docs: http://{self._settings.host}:{self._settings.port}/docs")
        logger.info("=" * 60)
    
    def _shutdown(self) -> None:
        """Application shutdown tasks."""
        logger.info("🛑 Shutting down...")
        self._cleanup_manager.stop()
        logger.info("✅ Shutdown complete")
    
    def _load_catalog(self) -> None:
        """Load product catalog."""
        try:
            products_path = self._settings.products_path
            if products_path.exists():
                catalog = init_catalog(products_path)
                logger.info(f"✅ Loaded {len(catalog.products)} products")
            else:
                logger.warning(f"⚠️ Products file not found: {products_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load catalog: {e}")
    
    def _configure_middleware(self, app: FastAPI) -> None:
        """Configure application middleware."""
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self._settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _register_routers(self, app: FastAPI) -> None:
        """Register API routers."""
        # REST API routes
        app.include_router(api_router)
        
        # WebSocket routes
        app.include_router(scanner_router)
        app.include_router(picker_router)
        app.include_router(requester_router)
    
    def _register_root(self, app: FastAPI) -> None:
        """Register root endpoint."""
        
        @app.get("/", response_class=HTMLResponse)
        async def root():
            """Redirect to modern frontend landing page."""
            return RedirectResponse(url="/static/pages/index.html")
    
    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self._app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

# Create application instance
application = Application()
app = application.app


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )
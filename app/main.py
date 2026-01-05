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
            """Serve API landing page."""
            return self._get_landing_page()
    
    def _get_landing_page(self) -> str:
        """Generate HTML landing page."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self._settings.app_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 60px 40px;
            border-radius: 24px;
            max-width: 600px;
            text-align: center;
        }}
        h1 {{ font-size: 2.5rem; margin-bottom: 16px; }}
        .status {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(16, 185, 129, 0.3);
            padding: 12px 24px;
            border-radius: 20px;
            margin: 20px 0;
        }}
        .dot {{
            width: 10px;
            height: 10px;
            background: #10b981;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .links {{ margin-top: 30px; }}
        a {{
            color: white;
            background: rgba(255,255,255,0.2);
            padding: 14px 28px;
            border-radius: 12px;
            text-decoration: none;
            display: inline-block;
            margin: 8px;
            font-weight: 600;
            border: 2px solid rgba(255,255,255,0.3);
            transition: all 0.2s;
        }}
        a:hover {{ 
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }}
        .info {{ margin-top: 40px; font-size: 0.9rem; opacity: 0.8; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📦 {self._settings.app_name}</h1>
        <p>Warehouse Pick System</p>
        
        <div class="status">
            <div class="dot"></div>
            <strong>Status: Running</strong>
        </div>
        
        <div class="links">
            <a href="/docs">📖 API Docs</a>
            <a href="/redoc">📚 ReDoc</a>
            <a href="/api/v1/health">❤️ Health</a>
        </div>
        
        <div class="info">
            <p>Environment: {self._settings.app_env}</p>
            <p>Version: 1.0.0</p>
        </div>
    </div>
</body>
</html>
"""
    
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

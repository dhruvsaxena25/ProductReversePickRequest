"""
==============================================================================
Application Settings Module
==============================================================================

Production-grade configuration management using Pydantic Settings.

This module implements the Singleton pattern to ensure a single global
configuration instance throughout the application lifecycle.

Features:
---------
- Environment variable loading with type validation
- .env file support for local development
- Computed properties for derived values
- Thread-safe singleton implementation

Configuration Priority (highest to lowest):
------------------------------------------
1. Environment variables
2. .env file
3. Default values

Security Considerations:
-----------------------
- Never commit .env files to version control
- Use strong JWT_SECRET_KEY in production
- Change default admin credentials immediately

==============================================================================
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Module logger
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    This class uses Pydantic Settings to provide type-safe configuration
    with automatic environment variable loading and validation.
    
    Attributes:
        app_name: Display name for the application
        app_env: Environment mode (development/staging/production)
        debug: Enable debug mode for verbose logging
        host: Server bind address
        port: Server port number
        database_url: SQLAlchemy database connection string
        jwt_secret_key: Secret key for JWT token signing
        jwt_algorithm: Algorithm for JWT signing (e.g., HS256)
        access_token_expire_minutes: Access token lifetime in minutes
        refresh_token_expire_days: Refresh token lifetime in days
        default_admin_username: Initial admin account username
        default_admin_password: Initial admin account password
        pick_timeout_minutes: Inactivity timeout for pick requests
        auto_cleanup_enabled: Enable automatic cleanup task
        auto_cleanup_hours: Delete completed requests older than this
        cleanup_interval_minutes: Cleanup task interval
        auto_mode_threshold: Quantity threshold for picking mode
        log_directory: Directory for pick completion logs
        products_file: Path to product catalog JSON
        cors_origins: Allowed CORS origins (JSON array string)
    
    Example:
        >>> settings = Settings()
        >>> print(settings.app_name)
        'Barcode Scanner API'
        >>> print(settings.is_production)
        False
    """
    
    # =========================================================================
    # PYDANTIC SETTINGS CONFIGURATION
    # =========================================================================
    model_config = SettingsConfigDict(
        # Load from .env file if present
        env_file=".env",
        env_file_encoding="utf-8",
        # Environment variables are case-insensitive
        case_sensitive=False,
        # Ignore extra environment variables
        extra="ignore",
        # Validate default values
        validate_default=True,
    )
    
    # =========================================================================
    # APPLICATION SETTINGS
    # =========================================================================
    app_name: str = Field(
        default="Barcode Scanner API",
        description="Display name for the application"
    )
    
    app_env: str = Field(
        default="development",
        description="Environment mode: development, staging, production"
    )
    
    debug: bool = Field(
        default=True,
        description="Enable debug mode for verbose logging"
    )
    
    # =========================================================================
    # SERVER SETTINGS
    # =========================================================================
    host: str = Field(
        default="0.0.0.0",
        description="Server bind address"
    )
    
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port number"
    )
    
    # =========================================================================
    # DATABASE SETTINGS
    # =========================================================================
    database_url: str = Field(
        default="sqlite:///./storage/db/warehouse.db",
        description="SQLAlchemy database connection string"
    )
    
    # =========================================================================
    # JWT AUTHENTICATION SETTINGS
    # =========================================================================
    jwt_secret_key: str = Field(
        default="change-this-in-production",
        min_length=16,
        description="Secret key for JWT token signing"
    )
    
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm for JWT signing"
    )
    
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,  # Max 24 hours
        description="Access token lifetime in minutes"
    )
    
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=90,  # Max 90 days
        description="Refresh token lifetime in days"
    )
    
    # =========================================================================
    # DEFAULT ADMIN SETTINGS
    # =========================================================================
    default_admin_username: str = Field(
        default="admin",
        min_length=3,
        max_length=50,
        description="Initial admin account username"
    )
    
    default_admin_password: str = Field(
        default="admin123",
        min_length=6,
        description="Initial admin account password"
    )
    
    # =========================================================================
    # PICK SYSTEM SETTINGS
    # =========================================================================
    pick_timeout_minutes: int = Field(
        default=30,
        ge=5,
        le=480,  # Max 8 hours
        description="Inactivity timeout for pick requests"
    )
    
    auto_cleanup_enabled: bool = Field(
        default=True,
        description="Enable automatic cleanup of old requests"
    )
    
    auto_cleanup_hours: int = Field(
        default=24,
        ge=1,
        le=720,  # Max 30 days
        description="Delete completed requests older than this"
    )
    
    cleanup_interval_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,  # Max 24 hours
        description="Cleanup task interval in minutes"
    )
    
    auto_mode_threshold: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Quantity threshold for picking mode selection"
    )
    
    # =========================================================================
    # FILE PATH SETTINGS
    # =========================================================================
    log_directory: str = Field(
        default="storage/logs",
        description="Directory for pick completion logs"
    )
    
    products_file: str = Field(
        default="data/products.json",
        description="Path to product catalog JSON"
    )
    
    # =========================================================================
    # CORS SETTINGS
    # =========================================================================
    cors_origins: str = Field(
        default='["*"]',
        description="Allowed CORS origins as JSON array string"
    )
    
    # =========================================================================
    # VALIDATORS
    # =========================================================================
    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        """
        Validate and normalize application environment.
        
        Args:
            value: Raw environment value
            
        Returns:
            Lowercase normalized environment name
            
        Raises:
            ValueError: If environment is not recognized
        """
        valid_envs = {"development", "staging", "production"}
        normalized = value.lower().strip()
        
        if normalized not in valid_envs:
            logger.warning(
                f"Unknown environment '{value}', defaulting to 'development'"
            )
            return "development"
        
        return normalized
    
    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        """
        Validate JWT algorithm is supported.
        
        Args:
            value: JWT algorithm name
            
        Returns:
            Validated algorithm name
            
        Raises:
            ValueError: If algorithm is not supported
        """
        supported = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        
        if value.upper() not in supported:
            raise ValueError(
                f"Unsupported JWT algorithm: {value}. "
                f"Supported: {', '.join(supported)}"
            )
        
        return value.upper()
    
    # =========================================================================
    # COMPUTED PROPERTIES
    # =========================================================================
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.app_env == "staging"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"
    
    @property
    def log_path(self) -> Path:
        """
        Get log directory as Path object.
        
        Creates the directory if it doesn't exist.
        
        Returns:
            Path object pointing to log directory
        """
        path = Path(self.log_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def products_path(self) -> Path:
        """
        Get products file as Path object.
        
        Returns:
            Path object pointing to products JSON file
        """
        return Path(self.products_file)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """
        Parse CORS origins from JSON string to list.
        
        Returns:
            List of allowed origin strings
        """
        try:
            origins = json.loads(self.cors_origins)
            if isinstance(origins, list):
                return origins
            return ["*"]
        except json.JSONDecodeError:
            logger.warning(
                f"Invalid CORS origins JSON: {self.cors_origins}, "
                "defaulting to ['*']"
            )
            return ["*"]
    
    @property
    def access_token_expire_seconds(self) -> int:
        """Get access token expiry in seconds."""
        return self.access_token_expire_minutes * 60
    
    @property
    def refresh_token_expire_seconds(self) -> int:
        """Get refresh token expiry in seconds."""
        return self.refresh_token_expire_days * 24 * 60 * 60
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    def get_database_path(self) -> Optional[Path]:
        """
        Extract database file path for SQLite databases.
        
        Returns:
            Path to database file, or None for non-SQLite databases
        """
        if self.database_url.startswith("sqlite"):
            # Extract path from SQLite URL
            db_path = self.database_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                db_path = db_path[2:]
            return Path(db_path)
        return None
    
    def ensure_directories(self) -> None:
        """
        Create all required directories.
        
        Creates:
        - Log directory
        - Database directory (for SQLite)
        """
        # Ensure log directory exists
        self.log_path.mkdir(parents=True, exist_ok=True)
        
        # Ensure database directory exists (SQLite only)
        db_path = self.get_database_path()
        if db_path:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug("Required directories created/verified")
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"Settings(app_name={self.app_name!r}, "
            f"app_env={self.app_env!r}, "
            f"debug={self.debug})"
        )


# =============================================================================
# SINGLETON INSTANCE MANAGEMENT
# =============================================================================

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the global Settings instance (singleton pattern).
    
    Uses lru_cache to ensure only one Settings instance is created
    throughout the application lifecycle. This is thread-safe and
    provides consistent configuration access.
    
    Returns:
        Global Settings instance
        
    Example:
        >>> settings = get_settings()
        >>> print(settings.app_name)
        'Barcode Scanner API'
    """
    settings = Settings()
    
    # Ensure required directories exist
    settings.ensure_directories()
    
    # Log configuration summary (only in debug mode)
    if settings.debug:
        logger.info(f"Configuration loaded: {settings}")
    
    return settings


# =============================================================================
# MODULE-LEVEL CONVENIENCE
# =============================================================================

# Create a module-level alias for backward compatibility
settings = get_settings()

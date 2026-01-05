"""
Application Settings

Pydantic-based configuration management with environment variable support.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Priority: Environment variables > .env file > defaults
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ============================================
    # APPLICATION
    # ============================================
    app_name: str = Field(default="Barcode Scanner API")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    
    # ============================================
    # SERVER
    # ============================================
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # ============================================
    # DATABASE
    # ============================================
    database_url: str = Field(default="sqlite:///./storage/db/warehouse.db")
    
    # ============================================
    # JWT AUTHENTICATION
    # ============================================
    jwt_secret_key: str = Field(default="9f3c2e1a7b6d4a908c1e7f9b2a5d6c8e4f1b9a3d7e6c5b2a8f0e9d4c1b6a7")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    
    # ============================================
    # DEFAULT ADMIN
    # ============================================
    default_admin_username: str = Field(default="admin")
    default_admin_password: str = Field(default="admin123")
    
    # ============================================
    # PICK SYSTEM
    # ============================================
    pick_timeout_minutes: int = Field(default=30)
    auto_cleanup_enabled: bool = Field(default=True)
    auto_cleanup_hours: int = Field(default=24)
    cleanup_interval_minutes: int = Field(default=60)
    auto_mode_threshold: int = Field(default=10)
    
    # ============================================
    # PATHS
    # ============================================
    log_directory: str = Field(default="storage/logs")
    products_file: str = Field(default="data/products.json")
    
    # ============================================
    # CORS
    # ============================================
    cors_origins: str = Field(default='["*"]')
    
    # ============================================
    # COMPUTED PROPERTIES
    # ============================================
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env.lower() == "production"
    
    @property
    def log_path(self) -> Path:
        """Get log directory as Path object."""
        path = Path(self.log_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def products_path(self) -> Path:
        """Get products file as Path object."""
        return Path(self.products_file)
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string."""
        try:
            return json.loads(self.cors_origins)
        except json.JSONDecodeError:
            return ["*"]


# Global settings instance
settings = Settings()

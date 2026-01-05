"""
==============================================================================
Configuration Package
==============================================================================

Centralized configuration management using Pydantic Settings.

This package provides:
- Environment-based configuration loading
- Type-safe settings with validation
- Singleton pattern for global access

Usage:
------
    from app.config import get_settings, Settings
    
    # Get the global settings instance
    settings = get_settings()
    
    # Access configuration values
    print(settings.app_name)
    print(settings.database_url)

==============================================================================
"""

from .settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
]

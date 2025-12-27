"""Configuration management for a11yhood backend.

Loads settings from .env file with Pydantic validation. Supports dual-database mode
(SQLite for tests, Supabase for production) and optional OAuth credentials.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Validates and provides defaults for all configuration values.
    Use DATABASE_URL for SQLite (tests), or SUPABASE_URL/KEY for production.
    """
    model_config = SettingsConfigDict(env_file=os.getenv("ENV_FILE", ".env"), case_sensitive=True)
    
    # Database (SQLite for tests, Supabase for production)
    DATABASE_URL: Optional[str] = None  # SQLite: sqlite+aiosqlite:///./test.db
    
    # Supabase (optional if using SQLite for tests)
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""  # service_role key for backend
    SUPABASE_ANON_KEY: str = ""  # anon/public key
    
    # CORS - strict allowlist for security
    # Dev: Uses Vite proxy (https://localhost:5173 -> http://localhost:8000)
    # Prod: Set to actual frontend domain (e.g., https://a11yhood.com)
    FRONTEND_URL: str = "https://localhost:5173"
    PRODUCTION_URL: str = ""
    
    # Test mode settings
    TEST_MODE: bool = False
    TEST_SCRAPER_LIMIT: int = 5
    
    # GitHub API token for higher rate limits (optional)
    GITHUB_TOKEN: Optional[str] = None
    
    # Secret key for JWT
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    
    # OAuth (optional)
    THINGIVERSE_APP_ID: Optional[str] = None
    RAVELRY_APP_KEY: Optional[str] = None
    RAVELRY_APP_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    


@lru_cache()
def get_settings(env_file: str = ".env") -> Settings:
    """Get cached settings instance.
    
    Uses LRU cache to avoid re-parsing .env on every import.
    Allows env_file override for testing with isolated configurations.
    """
    return Settings(_env_file=env_file)


# Default settings instance (respects ENV_FILE when set)
settings = get_settings(os.getenv("ENV_FILE", ".env"))

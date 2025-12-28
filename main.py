"""Main application entry point for a11yhood API.

Sets up FastAPI app with CORS middleware and routes for the accessible product community.
All endpoints are organized by domain in routers/ and use database_adapter for dual DB support.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config import settings, load_settings_from_env
from routers import activities, blog_posts, collections, discussions, product_urls, products, ratings, requests, scrapers, sources, users
from services.database import get_db
from services.scheduled_scrapers import get_scheduled_scraper_service


app = FastAPI(
    title="a11yhood API",
    version="1.0.0",
    description="API for a11yhood - Accessible Product Community"
)

import os
import logging

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

logger = logging.getLogger(__name__)


@app.on_event("startup")
async def validate_security_configuration():
    """Validate critical security settings on startup.
    
    Prevents common misconfigurations that could compromise security.
    Raises RuntimeError for critical issues that must be fixed before running.
    """
    # Reload settings within the function so tests that patch environment
    # (e.g., startup security tests) observe the updated values without
    # weakening production behavior.
    # Use a fresh settings instance so env patches in tests are respected.
    local_settings = load_settings_from_env()
    
    # Detect production environment by checking for production indicators
    is_production = any([
        # Production Supabase URL (not localhost/dummy)
        local_settings.SUPABASE_URL and 
        "supabase.co" in local_settings.SUPABASE_URL and
        "dummy" not in local_settings.SUPABASE_URL,
        
        # Production domain in CORS
        local_settings.PRODUCTION_URL and 
        "localhost" not in local_settings.PRODUCTION_URL and
        local_settings.PRODUCTION_URL.strip(),
        
        # Explicit production environment variable
        os.getenv("ENVIRONMENT") == "production",
        os.getenv("ENV") == "production",
    ])
    
    # CRITICAL: Prevent TEST_MODE in production
    if local_settings.TEST_MODE and is_production:
        raise RuntimeError(
            "🚨 CRITICAL SECURITY ERROR: TEST_MODE=true in production environment!\n"
            "\n"
            "This bypasses authentication and allows anyone to impersonate users.\n"
            "\n"
            "Action required:\n"
            "  1. Set TEST_MODE=false in your .env file\n"
            "  2. Restart the application\n"
            "\n"
            "Production detected due to:\n"
            f"  - SUPABASE_URL: {local_settings.SUPABASE_URL}\n"
            f"  - PRODUCTION_URL: {local_settings.PRODUCTION_URL}\n"
        )
    
    # CRITICAL: Validate SECRET_KEY in production
    if is_production:
        if local_settings.SECRET_KEY == "dev-secret-key-change-in-production":
            raise RuntimeError(
                "🚨 CRITICAL SECURITY ERROR: Default SECRET_KEY in production!\n"
                "\n"
                "Using the default key compromises JWT token security.\n"
                "\n"
                "Action required:\n"
                "  1. Generate a secure key:\n"
                "     python -c 'import secrets; print(secrets.token_hex(32))'\n"
                "  2. Set SECRET_KEY in your .env file\n"
                "  3. Restart the application\n"
            )
        
        if len(local_settings.SECRET_KEY) < 32:
            raise RuntimeError(
            f"🚨 CRITICAL SECURITY ERROR: SECRET_KEY too short ({len(local_settings.SECRET_KEY)} chars)!\n"
                "\n"
                "Production requires a SECRET_KEY of at least 32 characters.\n"
                "\n"
                "Action required:\n"
                "  1. Generate a secure key:\n"
                "     python -c 'import secrets; print(secrets.token_hex(32))'\n"
                "  2. Set SECRET_KEY in your .env file\n"
                "  3. Restart the application\n"
            )
    
    # Warnings for development mode
    if local_settings.TEST_MODE:
        logger.warning(
            "⚠️  TEST_MODE enabled - Development authentication active\n"
            "   - Dev tokens (dev-token-*) will be accepted\n"
            "   - Mock user accounts will be available\n"
            "   - NEVER enable TEST_MODE in production!\n"
        )
    
    if local_settings.SECRET_KEY == "dev-secret-key-change-in-production" and not is_production:
        logger.warning(
            "⚠️  Using default SECRET_KEY in development\n"
            "   This is OK for local testing but generate a unique key for staging/production.\n"
        )
    
    # Log security configuration status
    logger.info(
        f"Security configuration validated:\n"
        f"  - Production mode: {is_production}\n"
        f"  - TEST_MODE: {local_settings.TEST_MODE}\n"
        f"  - SECRET_KEY length: {len(local_settings.SECRET_KEY)} chars\n"
        f"  - CORS origins: {len(get_cors_origins())} configured\n"
    )
    
    # Initialize scheduled scrapers (if not in test mode)
    if not local_settings.TEST_MODE:
        try:
            scheduler_service = get_scheduled_scraper_service()
            db = get_db()
            scheduler_service.initialize(db)
            scheduler_service.start()
            logger.info("Scheduled scraper service started")
        except Exception as e:
            logger.error(f"Failed to initialize scheduled scrapers: {e}")
            # Don't fail startup if scheduler fails, just log the error
    else:
        logger.info("Scheduled scrapers disabled in TEST_MODE")


@app.on_event("shutdown")
async def shutdown_scheduled_scrapers():
    """Stop scheduled scrapers on shutdown"""
    try:
        scheduler_service = get_scheduled_scraper_service()
        scheduler_service.stop()
        logger.info("Scheduled scraper service stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduled scrapers: {e}")

def get_cors_origins():
    """Build strict CORS allowlist from environment.
    
    Security: Never use wildcard origins with credentials.
    Dev uses Vite proxy, so only HTTPS localhost needs direct CORS access.
    Production must explicitly set FRONTEND_URL and PRODUCTION_URL.
    """
    origins = set()
    
    # Add configured frontend URLs
    if settings.FRONTEND_URL:
        origins.add(settings.FRONTEND_URL)
    if settings.PRODUCTION_URL:
        origins.add(settings.PRODUCTION_URL)
    
    # Dev mode: Allow HTTPS localhost (Vite dev server uses proxy for API calls)
    # HTTP variants not needed - Vite proxy handles the HTTPS->HTTP translation
    if settings.TEST_MODE:
        origins.update({
            "https://localhost:5173",
            "https://127.0.0.1:5173",
        })
    
    # Support additional origins via env var (comma-separated)
    extra = os.getenv("CORS_EXTRA_ORIGINS", "")
    if extra:
        origins.update(o.strip() for o in extra.split(",") if o.strip())
    
    return list(origins)

origins = get_cors_origins()

# ============================================================================
# Security Middleware
# ============================================================================

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Enable XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    
    # HSTS (only in production with HTTPS)
    if not settings.TEST_MODE:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    
    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions policy
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=()"
    )
    
    return response

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Explicit allowlist only
    allow_credentials=True,  # Required for Authorization headers
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Include OPTIONS for CORS preflight
    allow_headers=["*"],  # Allow all headers (browsers send various sec-fetch-* headers)
)

# Trusted hosts (prevent host header injection)
allowed_hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
# Allow testserver for TestClient in tests
if settings.TEST_MODE:
    allowed_hosts.append("testserver")

if settings.PRODUCTION_URL:
    host = settings.PRODUCTION_URL.replace("https://", "").replace("http://", "").split("/")[0]
    if host:
        allowed_hosts.append(host)
if settings.FRONTEND_URL:
    host = settings.FRONTEND_URL.replace("https://", "").replace("http://", "").split("/")[0]
    if host and host not in allowed_hosts:
        allowed_hosts.append(host)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

# Global exception handler
from services.error_handler import handle_exception
app.add_exception_handler(Exception, handle_exception)

# ============================================================================
# Root Endpoints
# ============================================================================

@app.get("/")
@limiter.limit("60/minute")  # Prevent abuse
async def root(request: Request):
    """API root endpoint."""
    return {
        "message": "a11yhood API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint (no rate limit for monitoring)."""
    # Load fresh settings to report current mode
    current_settings = load_settings_from_env()
    
    # Detect production environment
    is_production = any([
        current_settings.SUPABASE_URL and 
        "supabase.co" in current_settings.SUPABASE_URL and
        "dummy" not in current_settings.SUPABASE_URL,
        
        current_settings.PRODUCTION_URL and 
        "localhost" not in current_settings.PRODUCTION_URL and
        current_settings.PRODUCTION_URL.strip(),
        
        os.getenv("ENVIRONMENT") == "production",
        os.getenv("ENV") == "production",
    ])
    
    return {
        "status": "healthy",
        "mode": "production" if is_production else "development",
        "test_mode": current_settings.TEST_MODE,
        "database": "supabase" if current_settings.SUPABASE_URL and "dummy" not in current_settings.SUPABASE_URL else "sqlite"
    }


# Temporary stub endpoint to prevent 404s from frontend scraper log queries.
# Returns empty list until full scraper logging is implemented in backend.
@app.get("/api/scraping-logs")
async def get_scraping_logs(limit: int = 50):
    return []


@app.get("/api/scrapers/schedule")
async def get_scheduled_scrapers():
    """Get status of scheduled scrapers"""
    try:
        scheduler_service = get_scheduled_scraper_service()
        jobs = await scheduler_service.get_jobs()
        return {
            "status": "enabled" if scheduler_service.scheduler and scheduler_service.scheduler.running else "disabled",
            "jobs": jobs
        }
    except Exception as e:
        logger.error(f"Error getting scheduled scrapers status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "jobs": []
        }


# Include routers
app.include_router(products.router)
app.include_router(ratings.router)
app.include_router(discussions.router)
app.include_router(activities.router)
app.include_router(scrapers.router)
app.include_router(requests.router)
app.include_router(users.router)
app.include_router(product_urls.router)
app.include_router(collections.router)
app.include_router(blog_posts.router)
app.include_router(sources.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

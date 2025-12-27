"""Main application entry point for a11yhood API.

Sets up FastAPI app with CORS middleware and routes for the accessible product community.
All endpoints are organized by domain in routers/ and use database_adapter for dual DB support.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import activities, blog_posts, collections, discussions, product_urls, products, ratings, requests, scrapers, sources, users


app = FastAPI(
    title="a11yhood API",
    version="1.0.0",
    description="API for a11yhood - Accessible Product Community"
)

import os

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

# Security: Strict CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Explicit allowlist only
    allow_credentials=True,  # Required for Authorization headers
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Include OPTIONS for CORS preflight
    allow_headers=["Content-Type", "Authorization"],  # Explicit headers only
)

# Root endpoints
@app.get("/")
def root():
    return {
        "message": "a11yhood API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Temporary stub endpoint to prevent 404s from frontend scraper log queries.
# Returns empty list until full scraper logging is implemented in backend.
@app.get("/api/scraping-logs")
async def get_scraping_logs(limit: int = 50):
    return []


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

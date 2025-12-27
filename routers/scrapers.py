from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from supabase import Client

from models.scrapers import (
    ScrapingLogResponse,
    ScraperTriggerRequest,
    OAuthConfigCreate,
    OAuthConfigUpdate,
    OAuthConfigResponse,
)
from pydantic import BaseModel
from services.database import get_db
from services.auth import get_current_user
from services.scrapers import ScraperService, ScraperOAuth
from services.sources import extract_domain, find_source_for_domain
from services.id_generator import normalize_to_snake_case
from scrapers import ScraperUtilities
from scrapers.github import GitHubScraper
from scrapers.ravelry import RavelryScraper
from scrapers.thingiverse import ThingiverseScraper
from routers.products import get_product_tag_rows, get_tags_map, set_product_tags

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])


class LoadUrlRequest(BaseModel):
    """Request model for load-url endpoint"""
    url: str


async def _run_scraper_and_log(
    scraper_service: ScraperService,
    source: str,
    user_id: str,
    database: Client,
    access_token: Optional[str] = None,
    test_mode: bool = False,
    test_limit: int = 5,
):
    """Run a scraper and save the log to the database"""
    try:
        if source == "thingiverse":
            result = await scraper_service.scrape_thingiverse(
                access_token=access_token,
                test_mode=test_mode,
                test_limit=test_limit
            )
        elif source == "ravelry":
            result = await scraper_service.scrape_ravelry(
                access_token=access_token,
                test_mode=test_mode,
                test_limit=test_limit
            )
        elif source == "github":
            result = await scraper_service.scrape_github(
                test_mode=test_mode,
                test_limit=test_limit
            )
        else:
            result = {
                'source': source,
                'status': 'error',
                'error_message': f'Unknown source: {source}',
                'products_found': 0,
                'products_added': 0,
                'products_updated': 0,
                'duration_seconds': 0,
            }
        
        # Save log to database using ScraperUtilities
        ScraperUtilities.set_last_scrape_time(database, result['source'], result, user_id=user_id)
        
    except Exception as e:
        # Save error log using ScraperUtilities
        error_result = {
            'source': source,
            'products_found': 0,
            'products_added': 0,
            'products_updated': 0,
            'duration_seconds': 0,
            'status': 'error',
            'error_message': str(e),
        }
        ScraperUtilities.set_last_scrape_time(database, source, error_result, user_id=user_id)


@router.post("/trigger", response_model=dict)
async def trigger_scraper(
    request: ScraperTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Trigger a scraping job (admin only)
    Runs in background to avoid blocking
    """
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    scraper_service = ScraperService(db)
    
    # Get OAuth token from database
    access_token = None
    if request.source.value in ["thingiverse", "ravelry"]:
        config_response = db.table("oauth_configs").select("access_token").eq("platform", request.source.value).execute()
        
        if not config_response.data:
            raise HTTPException(
                status_code=400,
                detail=f"OAuth not configured for {request.source.value}. Please authorize in admin settings."
            )
        
        access_token = config_response.data[0].get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail=f"No access token found for {request.source.value}. Please authorize in admin settings."
            )
    
    # Start scraping in background
    background_tasks.add_task(
        _run_scraper_and_log,
        scraper_service=scraper_service,
        source=request.source.value,
        user_id=current_user["id"],
        database=db,
        access_token=access_token,
        test_mode=request.test_mode,
        test_limit=request.test_limit,
    )
    
    return {
        "message": f"Scraping started for {request.source.value}",
        "test_mode": request.test_mode,
        "test_limit": request.test_limit if request.test_mode else None,
    }


@router.post("/load-url")
async def load_url(
    request: LoadUrlRequest,
    db = Depends(get_db),
) -> dict:
    """
    Check if a product with this URL exists in the database.
    If it exists, return it.
    If it doesn't exist, scrape it, save it to the database, and return it.
    No auth required - used by public submission form.
    Validates URL against supported sources before processing.
    """
    url = request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    url = url.strip()

    # If no scheme provided, default to https:// for scraper compatibility
    if "://" not in url:
        url = f"https://{url}"
    
    # Validate URL against supported sources
    domain = extract_domain(url)
    if not domain:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    # Get supported sources from database
    try:
        supported_sources_response = db.table("supported_sources").select("domain, name").execute()
        supported_sources = supported_sources_response.data if supported_sources_response.data else []
    except Exception as e:
        # If supported_sources table doesn't exist or query fails, block to avoid silent bypass
        print(f"Warning: Could not query supported_sources table: {e}")
        raise HTTPException(
            status_code=400,
            detail="Supported sources configuration is unavailable; cannot process URL."
        )
    
    # Check if domain is supported (block when no sources configured)
    if not supported_sources:
        raise HTTPException(
            status_code=400,
            detail="No supported sources are configured yet."
        )

    determined_source = find_source_for_domain(domain, supported_sources)
    if not determined_source:
        raise HTTPException(
            status_code=400,
            detail=f"URL domain is not supported. Supported domains are: {', '.join([s['domain'] for s in supported_sources])}"
        )
    
    def is_image_url(value: Optional[str]) -> bool:
        if not value:
            return False
        v = value.lower()
        return v.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"))

    # First, check if product already exists in database
    existing = db.table("products").select("*").eq("url", url).limit(1).execute()
    if existing.data:
        product = existing.data[0]
        # Normalize fields for API response
        product["image_url"] = product.get("image")
        product["external_id"] = product.get("external_id")
        product["sourceUrl"] = product.get("url")
        
        # Attach tags
        pt_rows = get_product_tag_rows(db, [product["id"]])
        tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
        tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
        product["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
        
        # Get owner IDs
        editors_response = db.table("product_editors").select("user_id").eq("product_id", product["id"]).execute()
        product["ownerIds"] = [editor["user_id"] for editor in editors_response.data] if editors_response.data else []
        
        # If the stored image is missing or not an image, attempt a light re-scrape to refresh media
        if not is_image_url(product.get("image_url")):
            refreshed = None
            try:
                # Try GitHub
                github_scraper = GitHubScraper(db)
                if github_scraper.supports_url(url):
                    refreshed = await github_scraper.scrape_url(url)
            except Exception as e:
                print(f"GitHub scraper refresh error: {e}")

            if not refreshed:
                try:
                    config_response = db.table("oauth_configs").select("access_token").eq("platform", "ravelry").execute()
                    access_token = config_response.data[0].get("access_token") if config_response.data else None
                    ravelry_scraper = RavelryScraper(db, access_token)
                    if ravelry_scraper.supports_url(url):
                        refreshed = await ravelry_scraper.scrape_url(url)
                except Exception as e:
                    print(f"Ravelry scraper refresh error: {e}")

            if not refreshed:
                try:
                    config_response = db.table("oauth_configs").select("access_token").eq("platform", "thingiverse").execute()
                    access_token = config_response.data[0].get("access_token") if config_response.data else None
                    thingiverse_scraper = ThingiverseScraper(db, access_token)
                    if thingiverse_scraper.supports_url(url):
                        refreshed = await thingiverse_scraper.scrape_url(url)
                except Exception as e:
                    print(f"Thingiverse scraper refresh error: {e}")

            if refreshed and is_image_url(refreshed.get("imageUrl") or refreshed.get("image_url")):
                new_image = refreshed.get("imageUrl") or refreshed.get("image_url")
                db.table("products").update({"image": new_image}).eq("id", product["id"]).execute()
                product["image_url"] = new_image

        return {"success": True, "product": product, "source": "database"}
    
    # Product doesn't exist - try to scrape it
    scraped_data = None
    scraper_name = None
    
    # Try each scraper to see if it supports this URL
    try:
        # Try GitHub
        github_scraper = GitHubScraper(db)
        if github_scraper.supports_url(url):
            scraped_data = await github_scraper.scrape_url(url)
            scraper_name = "github"
    except Exception as e:
        # Log but continue to next scraper
        print(f"GitHub scraper error: {e}")
    
    if not scraped_data:
        try:
            # Try Ravelry
            config_response = db.table("oauth_configs").select("access_token").eq("platform", "ravelry").execute()
            access_token = config_response.data[0].get("access_token") if config_response.data else None
            ravelry_scraper = RavelryScraper(db, access_token)
            if ravelry_scraper.supports_url(url):
                scraped_data = await ravelry_scraper.scrape_url(url)
                scraper_name = "ravelry"
        except Exception as e:
            # Log but continue to next scraper
            print(f"Ravelry scraper error: {e}")
    
    if not scraped_data:
        try:
            # Try Thingiverse
            config_response = db.table("oauth_configs").select("access_token").eq("platform", "thingiverse").execute()
            access_token = config_response.data[0].get("access_token") if config_response.data else None
            thingiverse_scraper = ThingiverseScraper(db, access_token)
            if thingiverse_scraper.supports_url(url):
                scraped_data = await thingiverse_scraper.scrape_url(url)
                scraper_name = "thingiverse"
        except Exception as e:
            # Log but continue
            print(f"Thingiverse scraper error: {e}")
    
    if not scraped_data:
        return {"success": False, "message": "URL not supported by any scraper or scraping failed"}
    
    # Save scraped product to database
    db_data = {
        "name": scraped_data.get("name"),
        "description": scraped_data.get("description"),
        "url": url,
        "image": scraped_data.get("imageUrl") or scraped_data.get("image_url"),
        "source": scraped_data.get("source", scraper_name),
        "type": scraped_data.get("type", "Other"),
        "external_id": scraped_data.get("external_id"),
        # No created_by since this is a public scrape
    }
    
    # Remove None values
    db_insert = {k: v for k, v in db_data.items() if v is not None}
    # Ensure slug exists for Supabase; SQLite adapter also handles slugs but this keeps parity
    if "slug" not in db_insert or not db_insert.get("slug"):
        base = db_insert.get("name") or db_insert.get("url") or "product"
        db_insert["slug"] = normalize_to_snake_case(base) or "product"

    response = db.table("products").insert(db_insert).execute()
    
    if not response.data:
        return {"success": False, "message": "Failed to save scraped product to database"}
    
    # Get the saved product
    saved_product = response.data[0]
    saved_product["image_url"] = saved_product.get("image")
    saved_product["external_id"] = saved_product.get("external_id")
    saved_product["sourceUrl"] = saved_product.get("url")
    
    # Create tag relationships if provided
    if scraped_data.get("tags"):
        set_product_tags(db, saved_product["id"], scraped_data["tags"])
    
    # Attach tags for response
    pt_rows = get_product_tag_rows(db, [saved_product["id"]])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    saved_product["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
    
    # No owners since this is a public scrape
    saved_product["ownerIds"] = []
    
    return {"success": True, "product": saved_product, "source": "scraped"}



@router.get("/logs", response_model=list[ScrapingLogResponse])
async def get_scraping_logs(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get scraping logs (authenticated users)"""
    query = db.table("scraping_logs").select("*")
    
    if source:
        query = query.eq("source", source)
    
    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
    
    response = query.execute()
    return response.data


@router.post("/oauth/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """
    Handle OAuth callback for scraper platforms
    Exchanges code for access token and stores it
    """
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get OAuth config for this platform
    config_response = db.table("oauth_configs").select("*").eq("platform", platform).execute()
    
    if not config_response.data:
        raise HTTPException(status_code=404, detail=f"OAuth config not found for {platform}")
    
    config = config_response.data[0]
    
    try:
        if platform == "ravelry":
            token_data = await ScraperOAuth.get_ravelry_token(
                client_id=config["client_id"],
                client_secret=config["client_secret"],
                code=code,
                redirect_uri=config["redirect_uri"]
            )
        elif platform == "thingiverse":
            token_data = await ScraperOAuth.get_thingiverse_token(
                client_id=config["client_id"],
                client_secret=config["client_secret"],
                code=code,
                redirect_uri=config["redirect_uri"]
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
        
        # Store tokens securely (TODO: encrypt tokens)
        update_data = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "token_expires_at": token_data.get("expires_at"),
        }
        
        db.table("oauth_configs").update(update_data).eq("id", config["id"]).execute()
        
        return {"message": f"OAuth token saved for {platform}"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {str(e)}")


@router.post("/oauth/{platform}/save-token")
async def save_oauth_token(
    platform: str,
    token_data: dict,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Save OAuth token from frontend (admin only)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check if config exists, create if not
    config_response = db.table("oauth_configs").select("*").eq("platform", platform).execute()
    
    update_data = {
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
    }
    
    if config_response.data:
        # Update existing config
        db.table("oauth_configs").update(update_data).eq("platform", platform).execute()
    else:
        # Create new config with minimal data
        config_data = {
            "platform": platform,
            "client_id": token_data.get("client_id", ""),
            "client_secret": token_data.get("client_secret", ""),
            "redirect_uri": token_data.get("redirect_uri", ""),
            **update_data
        }
        db.table("oauth_configs").insert(config_data).execute()
    
    return {"message": f"Token saved for {platform}"}


@router.get("/oauth/{platform}/config")
async def get_oauth_config(
    platform: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Get OAuth configuration for a specific platform (admin only)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # For admin users, return all fields including access_token and app_name
    # (needed for platforms like Thingiverse that use Personal Access Tokens)
    response = db.table("oauth_configs").select("*").eq("platform", platform).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail=f"No OAuth config found for {platform}")
    
    config = response.data[0]
    
    # Add has_access_token flag for convenience
    has_token = bool(config.get("access_token"))
    
    return {
        **config,
        "has_access_token": has_token
    }


@router.get("/oauth-configs", response_model=list[OAuthConfigResponse])
async def get_oauth_configs(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Get OAuth configurations (admin only, without secrets)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    response = db.table("oauth_configs").select("id,platform,client_id,redirect_uri,created_at,updated_at").execute()
    return response.data


@router.post("/oauth-configs", response_model=OAuthConfigResponse, status_code=201)
async def create_oauth_config(
    config: OAuthConfigCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Create OAuth configuration (admin only)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config_data = config.model_dump()
    response = db.table("oauth_configs").insert(config_data).execute()
    
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create OAuth config")
    
    return response.data[0]


@router.put("/oauth-configs/{platform}", response_model=OAuthConfigResponse)
async def update_oauth_config(
    platform: str,
    config: OAuthConfigUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Update OAuth configuration (admin only)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = config.model_dump(exclude_unset=True)
    response = db.table("oauth_configs").update(update_data).eq("platform", platform).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="OAuth config not found")
    
    return response.data[0]


@router.delete("/oauth/{platform}/disconnect", status_code=204)
async def disconnect_oauth(
    platform: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Delete OAuth token for a platform (admin only)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Delete the entire oauth_configs entry for this platform
    response = db.table("oauth_configs").delete().eq("platform", platform).execute()
    
    if response.count == 0:
        raise HTTPException(status_code=404, detail=f"No OAuth config found for {platform}")
    
    return None


ALLOWED_SEARCH_PLATFORMS = {
    "github": "github",
    "thingiverse": "thingiverse",
    "ravelry": "ravelry_pa_categories",
}


def _load_search_terms(db, platform: str, fallback: list[str]) -> list[str]:
    row = db.table("scraper_search_terms").select("search_terms").eq("platform", platform).limit(1).execute()
    if row.data and len(row.data) > 0:
        terms = row.data[0].get("search_terms") or []
        if isinstance(terms, list) and terms:
            return terms
    return fallback


@router.get("/{platform}/search-terms", response_model=dict)
async def get_search_terms(
    platform: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Get current scraper search terms for a platform (admin only)."""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    key = ALLOWED_SEARCH_PLATFORMS.get(platform)
    if not key:
        raise HTTPException(status_code=404, detail="Unsupported platform")

    fallback = GitHubScraper.SEARCH_TERMS if platform == "github" else (
        ThingiverseScraper.SEARCH_TERMS if platform == "thingiverse" else RavelryScraper.PA_CATEGORIES
    )

    try:
        terms = _load_search_terms(db, key, fallback)
        return {"search_terms": terms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load search terms: {e}")


class UpdateSearchTermsRequest(BaseModel):
    search_terms: list[str]


@router.post("/{platform}/search-terms", response_model=dict)
async def update_search_terms(
    platform: str,
    request: UpdateSearchTermsRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Update scraper search terms for a platform (admin only)."""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    key = ALLOWED_SEARCH_PLATFORMS.get(platform)
    if not key:
        raise HTTPException(status_code=404, detail="Unsupported platform")

    # Validate search terms
    if not request.search_terms:
        raise HTTPException(status_code=400, detail="At least one search term is required")
    if len(request.search_terms) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 search terms allowed")
    for term in request.search_terms:
        if not term or not term.strip():
            raise HTTPException(status_code=400, detail="Search terms cannot be empty")
        if len(term) > 100:
            raise HTTPException(status_code=400, detail="Search terms must be 100 characters or less")

    sanitized = [term.strip() for term in request.search_terms]

    try:
        db.table("scraper_search_terms").upsert({
            "platform": key,
            "search_terms": sanitized,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist search terms: {e}")

    # Update runtime variables for immediate effect
    if platform == "github":
        GitHubScraper.SEARCH_TERMS = sanitized
    elif platform == "thingiverse":
        ThingiverseScraper.SEARCH_TERMS = sanitized
    elif platform == "ravelry":
        RavelryScraper.PA_CATEGORIES = sanitized

    return {
        "search_terms": sanitized,
        "message": f"Saved {len(sanitized)} search terms."
    }

# Backwards compatibility routes for GitHub
@router.get("/github/search-terms", response_model=dict)
async def legacy_get_github_search_terms(current_user: dict = Depends(get_current_user), db = Depends(get_db)):
    return await get_search_terms("github", current_user=current_user, db=db)


@router.post("/github/search-terms", response_model=dict)
async def legacy_update_github_search_terms(request: UpdateSearchTermsRequest, current_user: dict = Depends(get_current_user), db = Depends(get_db)):
    return await update_search_terms("github", request, current_user=current_user, db=db)

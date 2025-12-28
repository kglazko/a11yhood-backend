"""
Backend scraper service - handles OAuth and coordinates scraping
"""
import os
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

from scrapers.github import GitHubScraper
from scrapers.thingiverse import ThingiverseScraper
from scrapers.ravelry import RavelryScraper


class ScraperOAuth:
    """Handle OAuth flows for different platforms"""
    
    @staticmethod
    async def get_ravelry_token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange Ravelry OAuth code for access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://www.ravelry.com/oauth2/token',
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'client_id': client_id,
                    'client_secret': client_secret,
                }
            )
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    async def get_thingiverse_token(client_id: str, client_secret: str, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange Thingiverse OAuth code for access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://www.thingiverse.com/login/oauth/access_token',
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'client_id': client_id,
                    'client_secret': client_secret,
                }
            )
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    async def refresh_ravelry_token(client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
        """Refresh Ravelry access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://www.ravelry.com/oauth2/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': client_id,
                    'client_secret': client_secret,
                }
            )
            response.raise_for_status()
            return response.json()


class ScraperService:
    """Coordinate scraping operations"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    async def scrape_thingiverse(self, access_token: Optional[str], test_mode: bool = False, test_limit: int = 5) -> Dict[str, Any]:
        """Scrape Thingiverse for accessibility products"""
        scraper = ThingiverseScraper(self.supabase, access_token)
        # Load persisted search terms if available (single row with search_terms array)
        try:
            response = self.supabase.table("scraper_search_terms").select("search_terms").eq("platform", "thingiverse").limit(1).execute()
            terms = (response.data or [{}])[0].get("search_terms") if response.data else None
            if isinstance(terms, list) and terms:
                scraper.SEARCH_TERMS = terms
        except Exception:
            pass
        try:
            result = await scraper.scrape(test_mode=test_mode, test_limit=test_limit)
            return result
        finally:
            await scraper.close()
    
    async def scrape_ravelry(self, access_token: str, test_mode: bool = False, test_limit: int = 5) -> Dict[str, Any]:
        """Scrape Ravelry for accessibility patterns"""
        scraper = RavelryScraper(self.supabase, access_token)
        # Load persisted PA categories if available (single row with search_terms array)
        try:
            response = self.supabase.table("scraper_search_terms").select("search_terms").eq("platform", "ravelry_pa_categories").limit(1).execute()
            cats = (response.data or [{}])[0].get("search_terms") if response.data else None
            if isinstance(cats, list) and cats:
                scraper.PA_CATEGORIES = cats
        except Exception:
            pass
        try:
            result = await scraper.scrape(test_mode=test_mode, test_limit=test_limit)
            return result
        finally:
            await scraper.close()
    
    async def scrape_github(self, test_mode: bool = False, test_limit: int = 5) -> Dict[str, Any]:
        """Scrape GitHub for assistive technology repositories"""
        token: Optional[str] = None
        # Prefer stored token (set via admin UI), fall back to env for local/dev.
        try:
            config_response = self.supabase.table("oauth_configs").select("access_token").eq("platform", "github").execute()
            token = (config_response.data or [{}])[0].get("access_token") if config_response.data else None
        except Exception:
            token = None

        if not token:
            token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_ACCESS_TOKEN")

        scraper = GitHubScraper(self.supabase, access_token=token)
        # Load persisted search terms if available (normalized: one row per term)
        try:
            response = self.supabase.table("scraper_search_terms").select("search_terms").eq("platform", "github").limit(1).execute()
            terms = (response.data or [{}])[0].get("search_terms") if response.data else None
            if isinstance(terms, list) and terms:
                scraper.SEARCH_TERMS = terms
        except Exception:
            # If DB read fails, continue with default in-memory terms
            pass
        try:
            result = await scraper.scrape(test_mode=test_mode, test_limit=test_limit)
            return result
        finally:
            await scraper.close()

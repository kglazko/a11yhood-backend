"""
Backend scraper service - handles OAuth and coordinates scraping
"""
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
        # Load persisted search terms if available
        try:
            response = self.supabase.table("scraper_search_terms").select("search_terms").eq("platform", "thingiverse").limit(1).execute()
            if response.data and len(response.data) > 0:
                terms = response.data[0].get("search_terms") or []
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
        # Load persisted PA categories if available
        try:
            response = self.supabase.table("scraper_search_terms").select("search_terms").eq("platform", "ravelry_pa_categories").limit(1).execute()
            if response.data and len(response.data) > 0:
                cats = response.data[0].get("search_terms") or []
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
        scraper = GitHubScraper(self.supabase)
        # Load persisted search terms if available
        try:
            response = self.supabase.table("scraper_search_terms").select("search_terms").eq("platform", "github").limit(1).execute()
            if response.data and len(response.data) > 0:
                terms = response.data[0].get("search_terms") or []
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

"""
Thingiverse scraper for accessibility and assistive devices
Uses Thingiverse API with OAuth authentication
"""
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base_scraper import BaseScraper
from urllib.parse import quote


class ThingiverseScraper(BaseScraper):
    """
    Thingiverse scraper for accessibility and assistive devices
    
    Searches for 3D-printable accessibility aids and assistive devices
    """
    
    SEARCH_TERMS = [
        'accessibility',
        'assistive device',
        'arthritis grip',
        'adaptive tool',
        'mobility aid',
        'tremor stabilizer',
        'adaptive utensil'
    ]
    
    API_BASE_URL = 'https://api.thingiverse.com'
    REQUESTS_PER_MINUTE = 5
    RESULTS_PER_PAGE = 20
    
    def __init__(self, supabase_client, access_token: Optional[str] = None):
        super().__init__(supabase_client, access_token)
    
    def get_source_name(self) -> str:
        return 'scraped-thingiverse'
    
    def supports_url(self, url: str) -> bool:
        """Check if this URL is a Thingiverse URL"""
        return 'thingiverse.com' in url.lower()
    
    async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single Thingiverse thing URL"""
        try:
            if not self.access_token:
                return None
            
            # Extract thing ID from URL
            # Format: https://www.thingiverse.com/thing:123456
            import re
            match = re.search(r'thing:(\d+)', url)
            if not match:
                return None
            
            thing_id = match.group(1)
            
            # Fetch thing data from Thingiverse API
            thing_data = await self._fetch_thing_details(thing_id)
            if not thing_data:
                return None
            
            return self._create_product_dict(thing_data)
        except Exception as e:
            print(f"Error scraping Thingiverse URL: {e}")
            return None
    
    async def _fetch_thing_details(self, thing_id: str) -> Optional[Dict[str, Any]]:
        """Fetch thing details from Thingiverse API with debug output."""
        try:
            url = f"https://api.thingiverse.com/things/{thing_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = await self.client.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                print(
                    f"[Thingiverse] Thing details status={response.status_code} id={thing_id} "
                    f"body={response.text[:200]}"
                )
            response.raise_for_status()
            data = response.json()
            print(
                f"[Thingiverse] Got details id={thing_id} name={data.get('name')} "
                f"public_url={data.get('public_url')}"
            )
            return data
        except Exception as e:
            print(f"[Thingiverse] Error fetching Thingiverse thing id={thing_id}: {e}")
        return None
    
    async def scrape(self, test_mode: bool = False, test_limit: int = 5) -> Dict[str, Any]:
        """
        Scrape Thingiverse for accessibility products
        
        Args:
            test_mode: If True, only scrape limited items for testing
            test_limit: Number of items to scrape in test mode
            
        Returns:
            Dict with scraping results (products_found, products_added, etc.)
        """
        if not self.access_token:
            raise ValueError("Thingiverse access token is required")
        
        start_time = datetime.now()
        products_found = 0
        products_added = 0
        products_updated = 0
        print(
            "[Thingiverse] Starting scrape",
            f"test_mode={test_mode}",
            f"test_limit={test_limit}",
            f"token_len={len(self.access_token) if self.access_token else 0}"
        )
        
        try:
            for term in self.SEARCH_TERMS:
                if test_mode and products_found >= test_limit:
                    break
                
                things = await self._search_things(term)
                print(f"[Thingiverse] term='{term}' hits={len(things)}")
                
                for thing in things:
                    if test_mode and products_found >= test_limit:
                        break
                    
                    products_found += 1
                    print(f"[Thingiverse] Fetching details id={thing.get('id')} url={thing.get('public_url')}")
                    
                    # Fetch full thing details
                    thing_details = await self._fetch_thing_details(thing['id'])
                    
                    if not thing_details:
                        print(f"[Thingiverse] Skip id={thing.get('id')} (no details)")
                        continue
                    
                    # Check if product already exists by URL
                    url = thing_details.get('public_url') or f"https://www.thingiverse.com/thing:{thing['id']}"
                    existing = await self._product_exists(url)
                    print(f"[Thingiverse] Exists? {bool(existing)} url={url}")
                    
                    if existing:
                        # Update existing product
                        result = await self._update_product(existing["id"], thing_details)
                        if result:
                            products_updated += 1
                            print(f"[Thingiverse] Updated existing product url={url}")
                        else:
                            print(f"[Thingiverse] Failed to update existing product url={url}")
                    else:
                        # Add new product
                        result = await self._create_product(thing_details)
                        if result:
                            products_added += 1
                            print(f"[Thingiverse] Added product url={url}")
                        else:
                            print(f"[Thingiverse] Failed to add product url={url}")
            
            duration = (datetime.now() - start_time).total_seconds()
            print(
                "[Thingiverse] Finished scrape",
                f"found={products_found}",
                f"added={products_added}",
                f"updated={products_updated}",
                f"duration_sec={duration:.2f}"
            )
            
            return {
                'source': 'thingiverse',
                'products_found': products_found,
                'products_added': products_added,
                'products_updated': products_updated,
                'duration_seconds': duration,
                'status': 'success',
            }
            
        except Exception as e:
            print(f"[Thingiverse] Fatal scrape error: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            return {
                'source': 'thingiverse',
                'products_found': products_found,
                'products_added': products_added,
                'products_updated': products_updated,
                'duration_seconds': duration,
                'status': 'error',
                'error_message': str(e),
            }
    
    async def _search_things(self, term: str) -> List[Dict[str, Any]]:
        """Search Thingiverse for things matching a term"""
        # Encode the term to avoid breaking the path (spaces, special chars)
        safe_term = quote(term, safe="")
        url = f"{self.API_BASE_URL}/search/{safe_term}"
        params = {
            'type': 'things',
            'per_page': self.RESULTS_PER_PAGE,
            'page': 1,
            'sort': 'relevant',
        }
        
        try:
            response = await self.client.get(
                url,
                params=params,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Accept': 'application/json',
                }
            )
            response.raise_for_status()
            
            data = response.json()
            hits = data.get('hits', [])

            # Debug: surface empty search responses to help diagnose token/scope/search issues.
            if not hits:
                print(
                    f"[Thingiverse] Empty search results term='{term}' status={response.status_code} "
                    f"body={response.text[:300]}"
                )
            return hits
            
        except httpx.HTTPError as e:
            print(f"[Thingiverse] Error searching for term '{term}': {e}")
            return []
    
    def _is_image_url(self, url: Optional[str]) -> bool:
        if not url:
            return False
        url_lower = url.lower()
        return url_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'))

    def _create_product_dict(self, thing: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Thingiverse thing data to product dict"""
        # Extract image URL; avoid picking non-image assets (e.g., .stl)
        image = None
        if thing.get('default_image') and self._is_image_url(thing['default_image'].get('url')):
            image = thing['default_image'].get('url')
        elif thing.get('thumbnail') and self._is_image_url(thing['thumbnail']):
            image = thing['thumbnail']
        else:
            # Fallback: try images array and pick the largest valid image
            images = thing.get('images') or []
            for img in images:
                sizes = img.get('sizes') or []
                # Prefer the largest size first by reversing
                for size in reversed(sizes):
                    candidate = size.get('url')
                    if self._is_image_url(candidate):
                        image = candidate
                        break
                if image:
                    break
        
        # Extract tags
        tags = []
        if thing.get('tags'):
            raw_tags = [tag.get('name') or tag.get('tag') for tag in thing['tags'] if tag.get('name') or tag.get('tag')]
            # Deduplicate while preserving order
            seen = set()
            for tag in raw_tags:
                if tag not in seen:
                    seen.add(tag)
                    tags.append(tag)
        
        url = thing.get('public_url') or f"https://www.thingiverse.com/thing:{thing['id']}"
        
        # Try to get rating data; fall back to likes as a proxy for popularity
        rating = thing.get('rating')
        rating_count = thing.get('rating_count')
        
        # If no rating data, use likes/favorites as popularity metric
        if not rating_count:
            likes = thing.get('like_count', 0)
            favorites = thing.get('favorite_count', 0)
            popularity_count = max(likes, favorites, 0)
            # Convert popularity to a simple score: 1-5 based on count
            if popularity_count >= 50:
                rating = 5.0
            elif popularity_count >= 20:
                rating = 4.0
            elif popularity_count >= 5:
                rating = 3.0
            elif popularity_count > 0:
                rating = 2.0
            rating_count = popularity_count if popularity_count > 0 else None
        
        # Determine type based on thing properties (default to 3D Printed)
        product_type = 'Fabrication'
        categories = [cat.get('name', '').lower() for cat in thing.get('categories', [])]
        if any('laser' in cat or 'cut' in cat for cat in categories):
            product_type = 'Fabrication'
        
        return {
            'name': thing['name'],
            'description': thing.get('description', ''),
            'url': url,
            'image': image,
            'source': 'scraped-thingiverse',
            'type': product_type,
            'tags': tags,
            'scraped_at': datetime.now().isoformat(),
            'external_id': str(thing['id']),
            'source_rating': rating,
            'source_rating_count': rating_count,
            'external_data': {
                'rating': rating,
                'rating_count': rating_count,
                'stars': rating_count or 0,
                'likes': thing.get('like_count', 0),
                'favorites': thing.get('favorite_count', 0),
                'categories': [cat.get('name') for cat in thing.get('categories', [])],
            }
        }
    
    async def _create_product(self, thing: Dict[str, Any]) -> bool:
        """Create a new product from Thingiverse thing"""
        return await super()._create_product(thing)
    
    async def _update_product(self, product_id: str, thing: Dict[str, Any]) -> bool:
        """Update existing product with latest Thingiverse data"""
        return await super()._update_product(product_id, thing)

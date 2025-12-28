"""
Ravelry scraper for accessibility knitting/crochet patterns
Uses Ravelry API with OAuth2 authentication
"""
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base_scraper import BaseScraper


class RavelryScraper(BaseScraper):
    """
    Ravelry scraper for accessibility patterns
    
    Searches Ravelry's pattern-accessibility (PA) categories for
    knitting and crochet patterns designed for accessibility needs
    """
    
    PA_CATEGORIES = [
        'medical-device-access',
        'medical-device-accessory',
        'mobility-aid-accessor',
        'other-accessibility',
        'therapy-aid'
    ]
    
    API_BASE_URL = 'https://api.ravelry.com'
    REQUESTS_PER_MINUTE = 5
    RESULTS_PER_PAGE = 50
    MAX_PAGES_PER_CATEGORY = 10
    
    def __init__(self, supabase_client, access_token: Optional[str] = None):
        super().__init__(supabase_client, access_token)
        # Ravelry API expects OAuth2 bearer tokens; keep Accept by default for JSON responses
        default_headers = {"Accept": "application/json"}
        if access_token:
            default_headers["Authorization"] = f"Bearer {access_token}"
        self.client = httpx.AsyncClient(headers=default_headers)
    
    def get_source_name(self) -> str:
        return 'scraped-ravelry'
    
    def supports_url(self, url: str) -> bool:
        """Check if this URL is a Ravelry URL"""
        return 'ravelry.com' in url.lower()
    
    async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single Ravelry pattern/project URL"""
        try:
            if not self.access_token:
                return None
            
            # Extract pattern ID from URL
            # Format: https://www.ravelry.com/patterns/library/pattern-name or /projects/username/project-name
            import re
            
            # Try to extract pattern ID
            pattern_match = re.search(r'/patterns/library/([a-z0-9-]+)', url)
            if pattern_match:
                pattern_id = pattern_match.group(1)
                pattern_data = await self._fetch_pattern_details(pattern_id)
                if pattern_data:
                    return self._create_product_dict(pattern_data)
            
            return None
        except Exception as e:
            print(f"Error scraping Ravelry URL: {e}")
            return None
    
    async def scrape(self, test_mode: bool = False, test_limit: int = 5) -> Dict[str, Any]:
        """
        Scrape Ravelry for accessibility patterns
        
        Args:
            test_mode: If True, only scrape limited items for testing
            test_limit: Number of items to scrape in test mode
            
        Returns:
            Dict with scraping results (products_found, products_added, etc.)
        """
        if not self.access_token:
            raise ValueError("Ravelry access token is required")
        
        start_time = datetime.now()
        products_found = 0
        products_added = 0
        products_updated = 0
        
        try:
            for pa_category in self.PA_CATEGORIES:
                if test_mode and products_found >= test_limit:
                    break
                
                # Fetch patterns for this PA category with pagination
                for page in range(1, self.MAX_PAGES_PER_CATEGORY + 1):
                    if test_mode and products_found >= test_limit:
                        break
                    
                    patterns = await self._search_patterns(pa_category, page)
                    
                    if not patterns:
                        break  # No more results
                    
                    for pattern in patterns:
                        if test_mode and products_found >= test_limit:
                            break
                        
                        products_found += 1
                        
                        # Fetch full pattern details to get ratings, craft type, description, etc.
                        pattern_id = pattern.get('id')
                        full_pattern = await self._fetch_pattern_details(pattern_id)
                        
                        if not full_pattern:
                            print(f"[Ravelry] Failed to fetch details for pattern {pattern_id}, skipping")
                            continue
                        
                        # Check if product already exists by URL
                        url = f"https://www.ravelry.com/patterns/library/{full_pattern['permalink']}"
                        existing = await self._product_exists(url)
                        
                        if existing:
                            # Update existing product
                            result = await self._update_product(existing["id"], full_pattern)
                            if result:
                                products_updated += 1
                        else:
                            # Add new product
                            result = await self._create_product(full_pattern)
                            if result:
                                products_added += 1
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                'source': 'ravelry',
                'products_found': products_found,
                'products_added': products_added,
                'products_updated': products_updated,
                'duration_seconds': duration,
                'status': 'success',
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return {
                'source': 'ravelry',
                'products_found': products_found,
                'products_added': products_added,
                'products_updated': products_updated,
                'duration_seconds': duration,
                'status': 'error',
                'error_message': str(e),
            }
    
    async def _search_patterns(self, pa_category: str, page: int) -> List[Dict[str, Any]]:
        """Search Ravelry patterns by PA category"""
        url = f"{self.API_BASE_URL}/patterns/search.json"
        params = {
            'pa': pa_category,
            'page_size': self.RESULTS_PER_PAGE,
            'page': page,
            'sort': 'best',
        }
        
        try:
            await self._throttle_request()
            response = await self.client.get(
                url,
                params=params,
            )
            response.raise_for_status()
            
            data = response.json()
            patterns = data.get('patterns', [])
            
            return patterns
            
        except httpx.HTTPError as e:
            print(f"[Ravelry] Error searching PA category '{pa_category}' page {page}: {e}")
            return []
    
    async def _fetch_pattern_details(self, pattern_id: int | str) -> Optional[Dict[str, Any]]:
        """Fetch full pattern details by ID or permalink"""
        url = f"{self.API_BASE_URL}/patterns/{pattern_id}.json"
        
        try:
            await self._throttle_request()
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            pattern = data.get('pattern') or (data.get('patterns') or [None])[0]
            
            return pattern
        except httpx.HTTPError as e:
            print(f"[Ravelry] Error fetching pattern {pattern_id}: {e}")
            return None
    
    def _create_product_dict(self, pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Ravelry pattern data to product format"""
        # Extract image URL - try multiple sources
        image = None
        
        # Try first_photo first
        if pattern.get('first_photo'):
            if isinstance(pattern['first_photo'], dict):
                image = pattern['first_photo'].get('medium_url') or pattern['first_photo'].get('small_url') or pattern['first_photo'].get('thumbnail_url')
            elif isinstance(pattern['first_photo'], str):
                image = pattern['first_photo']
        
        # If no first_photo, try photos array
        if not image and pattern.get('photos'):
            photos = pattern['photos']
            if isinstance(photos, list) and len(photos) > 0:
                first_photo = photos[0]
                if isinstance(first_photo, dict):
                    image = first_photo.get('medium_url') or first_photo.get('small_url') or first_photo.get('thumbnail_url')
                elif isinstance(first_photo, str):
                    image = first_photo
        
        # Determine type from craft type
        product_type = 'Knitting'  # Default to knitting
        if pattern.get('craft'):
            craft_name = pattern['craft'].get('name', '').lower() if isinstance(pattern['craft'], dict) else str(pattern['craft']).lower()
            if 'crochet' in craft_name:
                product_type = 'Crochet'
            elif 'knit' in craft_name:
                product_type = 'Knitting'
        
        # Extract pattern type tags
        tags = []
        if pattern.get('pattern_type'):
            type_name = pattern['pattern_type'].get('name') if isinstance(pattern['pattern_type'], dict) else pattern['pattern_type']
            if type_name:
                tags.append(type_name)
        
        if pattern.get('pattern_categories'):
            for cat in pattern['pattern_categories']:
                cat_name = cat.get('name') if isinstance(cat, dict) else cat
                if cat_name:
                    tags.append(cat_name)
        
        # Add personal_attributes (accessibility tags)
        if pattern.get('personal_attributes'):
            for pa in pattern['personal_attributes']:
                if isinstance(pa, dict):
                    pa_name = pa.get('name') or pa.get('permalink', '').replace('-', ' ').title()
                    if pa_name:
                        tags.append(pa_name)
                elif isinstance(pa, str):
                    tags.append(pa)
        
        # Add designer name as a tag if available
        if pattern.get('designer'):
            designer_name = pattern['designer'].get('name') if isinstance(pattern['designer'], dict) else pattern['designer']
            if designer_name:
                tags.append(f"Designer: {designer_name}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        pattern_url = f"https://www.ravelry.com/patterns/library/{pattern['permalink']}"
        
        # Description: Use notes_html or fall back to designer info
        description = pattern.get('notes_html', '').strip()
        if not description and pattern.get('designer'):
            designer_name = pattern['designer'].get('name') if isinstance(pattern['designer'], dict) else pattern['designer']
            if designer_name:
                description = f"Pattern by {designer_name}"
        
        # Extract rating data from full pattern details
        rating = pattern.get('rating_average') or pattern.get('rating')
        rating_count = pattern.get('rating_count', 0)
        
        # Extract last updated timestamp from Ravelry
        # Ravelry provides 'updated_at' field for when the pattern was last modified
        source_last_updated = None
        updated_at = pattern.get('updated_at')
        if updated_at:
            try:
                # Ravelry returns ISO 8601 format
                source_last_updated = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            except Exception as e:
                print(f"[Ravelry] Failed to parse last updated date: {e}")
        
        return {
            'name': pattern['name'],
            'description': description,
            'url': pattern_url,
            'image': image,
            'source': 'scraped-ravelry',
            'type': product_type,
            'tags': unique_tags,
            'scraped_at': datetime.now(),
            'external_id': str(pattern['id']),
            'source_rating': rating,
            'source_rating_count': rating_count,
            'source_last_updated': source_last_updated,
            'external_data': {
                'rating': rating,
                'rating_count': rating_count,
                'craft': pattern.get('craft', {}).get('name') if isinstance(pattern.get('craft'), dict) else pattern.get('craft'),
                'pattern_type': pattern.get('pattern_type', {}).get('name') if isinstance(pattern.get('pattern_type'), dict) else pattern.get('pattern_type'),
                'free': pattern.get('free'),
                'designer': pattern.get('designer', {}).get('name') if isinstance(pattern.get('designer'), dict) else pattern.get('designer'),
                'personal_attributes': pattern.get('personal_attributes', []),
            }
        }
    
    async def _create_product(self, pattern: Dict[str, Any]) -> bool:
        """Create a new product from Ravelry pattern"""
        return await super()._create_product(pattern)
    
    async def _update_product(self, product_id: str, pattern: Dict[str, Any]) -> bool:
        """Update existing product with latest Ravelry data"""
        return await super()._update_product(product_id, pattern)

"""
AbleData scraper using 2017 version with category-based browsing.

This scraper accesses archived AbleData pages via the Wayback Machine,
starting from the products-by-category page and extracting products
from each category listing.
"""

import asyncio
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper


class AbleDataScraper(BaseScraper):
    """Scraper for AbleData assistive technology database via Wayback Machine (2017 version)."""
    
    # Main category index page from 2017
    CATEGORY_INDEX_URL = "https://web.archive.org/web/20171201151646/http://www.abledata.com/products-by-category"
    
    # Known categories from the 2017 site structure
    CATEGORIES = [
        "Aids for Daily Living",
        "Blind and Low Vision",
        "Communication",
        "Computers",
        "Controls",
        "Deaf And Hard of Hearing",
        "Deaf Blind",
        "Education",
        "Environmental Adaptations",
        "Housekeeping",
        "Orthotics",
        "Prosthetics",
        "Recreation",
        "Safety and Security",
        "Seating",
        "Therapeutic Aids",
        "Transportation",
        "Walking",
        "Wheeled Mobility",
        "Workplace"
    ]
    
    API_BASE_URL = 'https://archive.org/wayback/available'
    WAYBACK_BASE = 'https://web.archive.org/web'
    REQUESTS_PER_MINUTE = 15  # Be respectful of archive.org
    
    def __init__(self, supabase_client, access_token: Optional[str] = None):
        super().__init__(supabase_client, access_token)
        self.session_products = set()  # Track URLs to avoid duplicates in a session
    
    def get_source_name(self) -> str:
        return "abledata"
    
    def _create_product_dict(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AbleDataScraper already builds complete product dicts, so just return as-is.
        
        Args:
            raw_data: Already-formatted product dict from _extract_product_details
            
        Returns:
            The product dict ready for database insertion
        """
        return raw_data
    
    async def scrape(
        self,
        search_terms: Optional[List[str]] = None,
        test_mode: bool = False,
        test_limit: int = 5
    ) -> Dict[str, Any]:
        """
        Scrape AbleData products by category.
        
        Args:
            search_terms: List of category page URLs to scrape (if None, fetches from database)
            test_mode: If True, limits scraping for testing
            test_limit: Maximum number of categories to scrape in test mode
            
        Returns:
            Dict with scraping results
        """
        results = {
            'source': self.get_source_name(),
            'products_found': 0,
            'products_added': 0,
            'products_updated': 0,
            'errors': []
        }
        
        try:
            # Get category URLs to scrape
            if search_terms is None:
                # Fetch from scraper_search_terms table
                search_terms = await self._get_search_terms()
            
            if not search_terms:
                # Default to known categories - we'll construct URLs for them
                search_terms = [self.CATEGORY_INDEX_URL]
            
            # Process each category URL
            for i, url in enumerate(search_terms):
                if test_mode and i >= test_limit:
                    print(f"[AbleData] Test mode: stopping after {test_limit} categories")
                    break
                
                try:
                    print(f"[AbleData] Processing URL {i+1}/{len(search_terms)}: {url}")
                    
                    # If this is the main index, extract category links
                    if 'products-by-category' in url:
                        category_urls = await self._extract_category_links(url)
                        for cat_url in category_urls:
                            if test_mode and results['products_found'] >= test_limit:
                                break
                            await self._scrape_category_page(cat_url, results, test_mode, test_limit)
                    else:
                        # Direct category page URL
                        await self._scrape_category_page(url, results, test_mode, test_limit)
                
                except Exception as e:
                    error_msg = f"Error processing {url}: {str(e)}"
                    print(f"[AbleData] {error_msg}")
                    results['errors'].append(error_msg)
        
        except Exception as e:
            error_msg = f"Fatal error in scrape: {str(e)}"
            print(f"[AbleData] {error_msg}")
            results['errors'].append(error_msg)
        
        return results
    
    async def _extract_category_links(self, index_url: str) -> List[str]:
        """
        Extract category page links from the main products-by-category page.
        
        Args:
            index_url: URL of the category index page
            
        Returns:
            List of category page URLs
        """
        category_urls = []
        
        try:
            # Fetch the index page
            html = await self._fetch_archived_page(index_url)
            if not html:
                return category_urls
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Look for category links - they should be headings or prominently displayed links
            # The 2017 site structure has categories as headings with links
            for heading in soup.find_all(['h2', 'h3', 'h4']):
                link = heading.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    category_name = link.get_text(strip=True)
                    
                    # Check if this matches our known categories
                    if category_name in self.CATEGORIES:
                        # Convert to absolute URL
                        if href.startswith('http'):
                            full_url = href
                        else:
                            # Construct full URL - may need to handle Wayback URLs specially
                            if 'web.archive.org' in index_url:
                                # Extract the original URL from the Wayback URL
                                match = re.search(r'web\.archive\.org/web/\d+/(.*)', index_url)
                                if match:
                                    base_url = match.group(1)
                                    full_url = urljoin(base_url, href)
                                    # Wrap in Wayback URL with same timestamp
                                    timestamp_match = re.search(r'web/(\d+)/', index_url)
                                    if timestamp_match:
                                        timestamp = timestamp_match.group(1)
                                        full_url = f"https://web.archive.org/web/{timestamp}/{full_url}"
                            else:
                                full_url = urljoin(index_url, href)
                        
                        category_urls.append(full_url)
                        print(f"[AbleData] Found category: {category_name} -> {full_url}")
            
            # Also check for direct links in the page content
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # Look for links that might be category pages
                if (text in self.CATEGORIES and 
                    'abledata.com' in href and
                    href not in category_urls):
                    
                    # Make absolute URL
                    if not href.startswith('http'):
                        # Check if href is already a Wayback path (starts with //web/ or /web/)
                        if href.startswith('//web/'):
                            # Protocol-relative Wayback path
                            href = f"https:{href}"
                        elif href.startswith('/web/'):
                            # Root-relative Wayback path
                            href = f"https://web.archive.org{href}"
                        elif 'web.archive.org' in index_url:
                            # Regular relative path - wrap in Wayback URL
                            timestamp_match = re.search(r'web/(\d+)/', index_url)
                            if timestamp_match:
                                timestamp = timestamp_match.group(1)
                                href = f"https://web.archive.org/web/{timestamp}/{href}"
                        else:
                            href = urljoin(index_url, href)
                    
                    category_urls.append(href)
                    print(f"[AbleData] Found category link: {text} -> {href}")
        
        except Exception as e:
            print(f"[AbleData] Error extracting category links: {str(e)}")
        
        return category_urls
    
    async def _scrape_category_page(self, category_url: str, results: Dict[str, Any], test_mode: bool = False, test_limit: int = 5):
        """
        Scrape products from a single category page.
        Two-phase approach:
        1. Extract product links and thumbnail images from category listing
        2. Fetch full details from each product's detail page
        
        Args:
            category_url: URL of the category page
            results: Results dict to update with findings
            test_mode: If True, limits scraping for testing
            test_limit: Maximum number of products to scrape in test mode
        """
        try:
            # Phase 1: Fetch the category listing page
            html = await self._fetch_archived_page(category_url)
            if not html:
                return
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract basic product info (links and images) from listing
            products_basic = await self._extract_products_from_listing(soup, category_url)
            
            print(f"[AbleData] Found {len(products_basic)} products on category page")
            
            # Phase 2: Fetch details for each product
            for base_info in products_basic:
                # Check test_mode limit before processing each product
                if test_mode and results['products_found'] >= test_limit:
                    print(f"[AbleData] Test mode: stopping after {test_limit} products")
                    break
                
                try:
                    # Get full product details from detail page
                    product_data = await self._extract_product_details(base_info['url'], base_info)
                    
                    if not product_data:
                        continue
                    
                    # Check if product already exists
                    existing = await self._product_exists(product_data['url'])
                    
                    if existing:
                        # Update existing product
                        await self._update_product(existing['id'], product_data)
                        results['products_updated'] += 1
                    else:
                        # Create new product
                        await self._create_product(product_data)
                        results['products_added'] += 1
                    
                    results['products_found'] += 1
                    
                    banned_status = ' (BANNED)' if product_data.get('banned') else ''
                    rating_info = f" [{product_data.get('source_rating', 0):.1f}★]" if product_data.get('source_rating') else ''
                    print(f"[AbleData] Processed: {product_data['name']}{rating_info}{banned_status}")
                    
                except Exception as e:
                    print(f"[AbleData] Error processing product {base_info.get('url')}: {str(e)}")
                    continue
        
        except Exception as e:
            print(f"[AbleData] Error scraping category page {category_url}: {str(e)}")
            results['errors'].append(f"Category page error: {str(e)}")
    
    async def _extract_products_from_listing(
        self, 
        soup: BeautifulSoup, 
        page_url: str
    ) -> List[Dict[str, Any]]:
        """
        Extract product information from a category listing page.
        This extracts product links and thumbnail images.
        Full details will be fetched from individual product pages.
        
        Args:
            soup: BeautifulSoup object of the page
            page_url: URL of the page (for context and URL construction)
            
        Returns:
            List of product dicts with basic info and image URLs
        """
        products = []
        
        # First, collect all images by their alt text (product name)
        images_by_name = {}
        for img in soup.find_all('img'):
            alt_text = img.get('alt', '').strip()
            src = img.get('src', '')
            # Skip placeholders and non-product images
            if (alt_text and 
                src and 
                'ImageComingSoon' not in src and
                not any(skip in src.lower() for skip in ['logo', 'icon', 'button', 'arrow', 'banner', 'histats'])):
                
                # Make absolute URL
                if src.startswith('http'):
                    image_url = src
                elif src.startswith('/web/'):
                    image_url = f"https://web.archive.org{src}"
                else:
                    timestamp_match = re.search(r'web/(\\d+)/', page_url)
                    if timestamp_match:
                        timestamp = timestamp_match.group(1)
                        src = src.lstrip('/')
                        image_url = f"https://web.archive.org/web/{timestamp}im_/{src}"
                    else:
                        image_url = urljoin(page_url, src)
                
                images_by_name[alt_text] = image_url
        
        print(f"[AbleData] Found {len(images_by_name)} product images on category page")
        
        # Now find all product links
        product_links = soup.find_all('a', href=re.compile(r'/product/', re.I))
        
        for link in product_links:
            try:
                # Get product name from link text
                name = link.get_text(strip=True)
                if not name or len(name) < 3:
                    continue
                
                # Get product URL
                href = link.get('href', '')
                if not href or href in [p.get('url') for p in products]:
                    continue
                
                # Make absolute URL
                if href.startswith('http'):
                    product_url = href
                elif href.startswith('/web/'):
                    product_url = f"https://web.archive.org{href}"
                else:
                    timestamp_match = re.search(r'web/(\\d+)/', page_url)
                    if timestamp_match:
                        timestamp = timestamp_match.group(1)
                        href = href.lstrip('/')
                        product_url = f"https://web.archive.org/web/{timestamp}/{href}"
                    else:
                        product_url = urljoin(page_url, href)
                
                # Look up image by product name (alt text matching)
                image_url = images_by_name.get(name, None)
                
                products.append({
                    'name': name,
                    'url': product_url,
                    'image': image_url,
                    'source': self.get_source_name(),
                    'type': 'Assistive Technology'
                })
                
            except Exception as e:
                print(f"[AbleData] Error extracting product from listing: {str(e)}")
                continue
        
        return products
    
    async def _extract_product_details(self, product_url: str, base_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract detailed product information from product detail page.
        
        Args:
            product_url: URL of the product detail page
            base_info: Basic info from category listing (name, url, image_url)
            
        Returns:
            Complete product dict or None
        """
        try:
            # Fetch the product detail page
            html = await self._fetch_archived_page(product_url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract description and technical specifications
            description_parts = []
            
            # Extract body description
            body_div = soup.find('div', class_=re.compile(r'field-name-body.*field-type-text-with-summary.*field-label-hidden'))
            if body_div:
                body_text = body_div.get_text(strip=True)
                if body_text:
                    description_parts.append(body_text)
            
            # Extract technical specifications
            tech_div = soup.find('div', class_=re.compile(r'field-name-field-technical-specifications.*field-type-text-long'))
            if tech_div:
                # Create a copy of the div to manipulate
                tech_copy = BeautifulSoup(str(tech_div), 'html.parser')
                
                # Convert field-label divs to h2 headers
                for label_div in tech_copy.find_all('div', class_=re.compile(r'field-label', re.I)):
                    label_text = label_div.get_text(strip=True)
                    if label_text:
                        h2 = tech_copy.new_tag('h2')
                        h2.string = label_text
                        label_div.replace_with(h2)
                
                # Remove field-item divs but keep their content
                for item_div in tech_copy.find_all('div', class_=re.compile(r'field-item', re.I)):
                    # Replace div with its contents
                    item_div.unwrap()
                
                # Get text while preserving p, ul, li structure without over-stripping
                tech_text_parts = []
                for element in tech_copy.find_all(['h2', 'p', 'ul', 'li']):
                    if element.name == 'h2':
                        tech_text_parts.append(f"\n**{element.get_text(strip=True)}**\n")
                    elif element.name == 'p':
                        tech_text_parts.append(element.get_text(separator=' ', strip=True))
                    elif element.name == 'ul':
                        items = [f"- {li.get_text(separator=' ', strip=True)}" for li in element.find_all('li', recursive=False)]
                        tech_text_parts.extend(items)
                    elif element.name == 'li' and element.parent.name != 'ul':
                        tech_text_parts.append(f"- {element.get_text(separator=' ', strip=True)}")
                
                tech_text = '\n'.join(tech_text_parts)
                if tech_text.strip():
                    description_parts.append(f"\n**Technical Specifications:**\n{tech_text}")
            
            description = '\n\n'.join(description_parts) if description_parts else base_info.get('name')
            
            # Extract tags from selected categories
            # Only include items inside <li class="selected">
            tags = []
            
            # Find all li elements with class "selected"
            for selected_li in soup.find_all('li', class_='selected'):
                # Get the anchor tag inside the li
                anchor = selected_li.find('a')
                if anchor:
                    tag_text = anchor.get_text(strip=True)
                    if (tag_text and 
                        len(tag_text) > 3 and 
                        tag_text not in tags):
                        tags.append(tag_text)
            
            # Extract rating from specific HTML structure
            source_rating = None
            source_rating_count = None
            
            # Look for <li class="thumb-down"> containing <div class="percent">
            # Invert thumb-down percentage to get thumbs up rating
            thumb_down = soup.find('li', class_='thumb-down')
            if thumb_down:
                percent_div = thumb_down.find('div', class_='percent')
                if percent_div:
                    percent_text = percent_div.get_text(strip=True)
                    # Extract percentage number
                    percent_match = re.search(r'(\d+)%', percent_text)
                    if percent_match:
                        thumbs_down_percentage = int(percent_match.group(1))
                        # Invert to get thumbs up percentage, then convert to 5-star scale
                        thumbs_up_percentage = 100 - thumbs_down_percentage
                        source_rating = (thumbs_up_percentage / 100.0) * 5.0
            else:
                # Fallback to thumb-up if thumb-down doesn't exist
                thumb_up = soup.find('li', class_='thumb-up')
                if thumb_up:
                    percent_div = thumb_up.find('div', class_='percent')
                    if percent_div:
                        percent_text = percent_div.get_text(strip=True)
                        percent_match = re.search(r'(\d+)%', percent_text)
                        if percent_match:
                            thumbs_up_percentage = int(percent_match.group(1))
                            source_rating = (thumbs_up_percentage / 100.0) * 5.0
            
            # Look for <div class="rate-info"> for rating count
            rate_info = soup.find('div', class_='rate-info')
            if rate_info:
                rate_text = rate_info.get_text(strip=True)
                # Extract number of users
                count_match = re.search(r'(\d+)\s+users?', rate_text, re.IGNORECASE)
                if count_match:
                    source_rating_count = int(count_match.group(1))
            
            # Extract last updated date
            page_date = self._extract_date_from_page(soup)
            
            # Build complete product dict
            product = {
                'name': base_info.get('name'),
                'description': description,
                'url': base_info.get('url'),
                'image': base_info.get('image'),
                'source': self.get_source_name(),
                'type': 'Assistive Technology',
                'tags': tags if tags else None,
                'source_rating': source_rating,
                'source_rating_count': source_rating_count,
                'source_last_updated': page_date
            }
            
            # Check if product should be marked as banned
            if description and 'no longer sells assistive products' in description.lower():
                product['banned'] = True
                product['banned_reason'] = 'Company no longer sells assistive products'
            
            return product
            
        except Exception as e:
            print(f"[AbleData] Error extracting product details from {product_url}: {str(e)}")
            return None
    
    def _extract_date_from_page(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Extract the last updated date from the page.
        Checks for price check date div first, then common date patterns.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            datetime object or None
        """
        try:
            # First, try to find the price check date div
            price_check_div = soup.find('div', class_=re.compile(r'field-group-inline-item.*item-field_price_check_date', re.I))
            if price_check_div:
                date_text = price_check_div.get_text(strip=True)
                if date_text:
                    # Try to parse the date text
                    try:
                        return datetime.strptime(date_text, '%B %d, %Y')
                    except ValueError:
                        try:
                            return datetime.strptime(date_text, '%B %d %Y')
                        except ValueError:
                            try:
                                return datetime.strptime(date_text, '%m/%d/%Y')
                            except ValueError:
                                pass
            
            # Fallback: Look for common date patterns in page text
            text = soup.get_text()
            
            # Try to find "Last Updated" or similar phrases
            date_patterns = [
                r'Last Updated:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
                r'Updated:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
                r'Last Modified:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
                r'Date:?\s*([A-Za-z]+ \d{1,2},? \d{4})',
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    # Try to parse the date
                    try:
                        return datetime.strptime(date_str, '%B %d, %Y')
                    except ValueError:
                        try:
                            return datetime.strptime(date_str, '%B %d %Y')
                        except ValueError:
                            pass
        
        except Exception as e:
            print(f"[AbleData] Error extracting date: {str(e)}")
        
        return None
    
    async def _fetch_archived_page(self, wayback_url: str) -> Optional[str]:
        """
        Fetch an archived page from the Wayback Machine.
        
        Args:
            wayback_url: Full Wayback Machine URL
            
        Returns:
            HTML content or None
        """
        await self._throttle_request()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; AbleDataScraper/1.0)',
            'Accept-Encoding': 'identity'  # Disable automatic decompression
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(wayback_url, headers=headers)
                response.raise_for_status()
                return response.text
        
        except httpx.HTTPError as e:
            print(f"[AbleData] Error fetching archived page: {str(e)}")
            return None
    
    async def _throttle_request(self):
        """Rate limit requests to archive.org."""
        if not hasattr(self, '_last_request_time'):
            self._last_request_time = time.time()
            return
        
        elapsed = time.time() - self._last_request_time
        min_interval = 60.0 / self.REQUESTS_PER_MINUTE
        
        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()
    
    async def _get_search_terms(self) -> List[str]:
        """Fetch search terms (category URLs) from the database."""
        try:
            # Query the scraper_search_terms table
            response = self.supabase.table('scraper_search_terms').select('search_term').eq(
                'platform', 'abledata'
            ).execute()
            
            if response.data:
                return [item['search_term'] for item in response.data]
        
        except Exception as e:
            print(f"[AbleData] Error fetching search terms: {str(e)}")
        
        return []

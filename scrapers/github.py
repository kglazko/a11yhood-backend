"""
GitHub scraper for accessibility and assistive technology projects
Uses GitHub REST API to search for repositories focused on assistive technologies
"""
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
from .base_scraper import BaseScraper


class GitHubScraper(BaseScraper):
    """
    GitHub scraper for accessibility and assistive technology projects.
    
    Search strategy: Uses multiple targeted search terms to find diverse assistive tech.
    Focuses on tools and software that address disability access needs:
    - Screen readers and text-to-speech
    - Eye tracking and alternative input methods
    - Speech recognition and voice control
    - Switch access for severe motor disabilities
    - Mobility aids and assistive devices
    
    Filters out generic accessibility guidelines/documentation projects
    to focus on actual tools and software implementations.
    """
    
    SEARCH_TERMS = [
        'assistive technology',
        'screen reader',
        'eye tracking',
        'speech recognition',
        'switch access',
        'alternative input',
        'text-to-speech',
        'voice control',
        'accessibility aid',
        'mobility aid software'
    ]
    
    API_BASE_URL = 'https://api.github.com'
    REQUESTS_PER_MINUTE = 30
    MAX_PAGES_PER_TERM = 10
    RESULTS_PER_PAGE = 20
    
    def __init__(self, supabase_client):
        super().__init__(supabase_client)
    
    def get_source_name(self) -> str:
        return 'scraped-github'
    
    def supports_url(self, url: str) -> bool:
        """Check if this URL is a GitHub URL"""
        return 'github.com' in url.lower()
    
    async def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single GitHub repository URL"""
        try:
            # Extract owner/repo from URL
            # Format: https://github.com/owner/repo (additional path segments are ignored)
            parts = url.rstrip('/').split('/')
            if len(parts) < 5 or parts[2] != 'github.com':
                return None
            
            owner = parts[3]
            repo = parts[4]
            
            # Fetch repo data from GitHub API
            repo_data = await self._fetch_repo_details(owner, repo)
            if not repo_data:
                return None
            
            return self._create_product_dict(repo_data)
        except Exception as e:
            print(f"Error scraping GitHub URL: {e}")
            return None
    
    async def _fetch_repo_details(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Fetch repository details from GitHub API"""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}"
            response = await self.client.get(url, timeout=10.0)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching GitHub repo: {e}")
        return None
    
    async def scrape(self, test_mode: bool = False, test_limit: int = 5) -> Dict[str, Any]:
        """
        Scrape GitHub for accessibility repositories
        
        Args:
            test_mode: If True, only scrape limited items for testing
            test_limit: Number of items to scrape in test mode
            
        Returns:
            Dict with scraping results (products_found, products_added, etc.)
        """
        start_time = datetime.now()
        products_found = 0
        products_added = 0
        products_updated = 0
        
        try:
            for term_index, term in enumerate(self.SEARCH_TERMS):
                if test_mode and products_found >= test_limit:
                    break
                
                # Search repositories with this term
                for page in range(1, self.MAX_PAGES_PER_TERM + 1):
                    if test_mode and products_found >= test_limit:
                        break
                    
                    repos = await self._fetch_repositories(term, page)
                    
                    if not repos:
                        break  # No more results
                    
                    for repo in repos:
                        if test_mode and products_found >= test_limit:
                            break
                        
                        products_found += 1
                        
                        # Check if product already exists by URL
                        existing = await self._product_exists(repo["html_url"])
                        
                        if existing:
                            # Update existing product
                            result = await self._update_product(existing["id"], repo)
                            if result:
                                products_updated += 1
                        else:
                            # Add new product
                            result = await self._create_product(repo)
                            if result:
                                products_added += 1
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                'source': 'github',
                'products_found': products_found,
                'products_added': products_added,
                'products_updated': products_updated,
                'duration_seconds': duration,
                'status': 'success',
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return {
                'source': 'github',
                'products_found': products_found,
                'products_added': products_added,
                'products_updated': products_updated,
                'duration_seconds': duration,
                'status': 'error',
                'error_message': str(e),
            }
    
    async def _fetch_repositories(self, term: str, page: int) -> List[Dict[str, Any]]:
        """Fetch repositories from GitHub API for a search term"""
        quoted_term = f'"{term}"'
        url = f"{self.API_BASE_URL}/search/repositories"
        params = {
            'q': f'{quoted_term} stars:>5',
            'sort': 'stars',
            'order': 'desc',
            'per_page': self.RESULTS_PER_PAGE,
            'page': page,
        }
        
        try:
            response = await self.client.get(
                url,
                params=params,
                headers={'Accept': 'application/vnd.github.v3+json'}
            )
            response.raise_for_status()
            
            data = response.json()
            
            repos = []
            
            if data.get('items'):
                for item in data['items']:
                    # Less restrictive filter - just avoid pure documentation projects
                    if not self._is_documentation_only(item):
                        repos.append(item)
            
            return repos
            
        except httpx.HTTPError as e:
            print(f"[GitHub] HTTP Error fetching repositories for term '{term}': {e}")
            return []
        except Exception as e:
            print(f"[GitHub] Error fetching repositories for term '{term}': {type(e).__name__}: {e}")
            return []
    
    def _is_documentation_only(self, repo: Dict[str, Any]) -> bool:
        """Check if repository is pure documentation (no code)"""
        name = repo.get('name', '').lower()
        description = (repo.get('description') or '').lower()
        
        # Filter out known documentation-only repo patterns
        doc_patterns = ['awesome-', '-list', '-guide', 'guidelines', 'wcag', '-docs', '-l-']
        
        for pattern in doc_patterns:
            if pattern in name:
                return True

        if 'awesome' in description or 'list of' in description or 'curated' in description:
            return True
        if len(name.strip('-')) <= 2:  # extremely short names are likely lists/aggregators
            return True
        
        return False
    
    def _create_product_dict(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """Convert GitHub repo data to product dict"""
        # GitHub doesn't have ratings, but we can use stars as a proxy
        stars = repo.get('stargazers_count', 0)
        
        # Extract topics as tags
        topics = repo.get('topics', [])
        tags = []
        seen = set()
        
        if topics:
            # Deduplicate while preserving order (though topics should already be unique)
            for topic in topics:
                if topic and topic not in seen:
                    seen.add(topic)
                    tags.append(topic)
        
        # Add language as a tag if available
        language = repo.get('language')
        if language and language not in seen:
            tags.append(language)
        
        # Convert stars to a 5-star rating: normalize based on common thresholds
        # 0-10 stars = 2, 10-50 = 3, 50-100 = 4, 100+ = 5
        if stars >= 100:
            star_rating = 5.0
        elif stars >= 50:
            star_rating = 4.0
        elif stars >= 10:
            star_rating = 3.0
        elif stars > 0:
            star_rating = 2.0
        else:
            star_rating = None
        
        return {
            'name': repo['name'],
            'description': repo.get('description', ''),
            'url': repo['html_url'],
            'image': repo['owner'].get('avatar_url'),
            'source': 'scraped-github',
            'type': 'Software',
            'tags': tags,
            'scraped_at': datetime.now().isoformat(),
            'external_id': str(repo['id']),
            'source_rating': star_rating,  # Normalized star rating (2-5)
            'source_rating_count': stars,  # Actual GitHub star count
            'external_data': {
                'language': language,
                'topics': topics,
            }
        }
    
    async def _create_product(self, repo: Dict[str, Any]) -> bool:
        """Create a new product from GitHub repository"""
        return await super()._create_product(repo)
    
    async def _update_product(self, product_id: str, repo: Dict[str, Any]) -> bool:
        """Update existing product with latest GitHub data"""
        return await super()._update_product(product_id, repo)

"""Scraper implementations for different platforms"""

from .base_scraper import BaseScraper, ScraperUtilities
from .github import GitHubScraper
from .thingiverse import ThingiverseScraper
from .ravelry import RavelryScraper

__all__ = [
    'BaseScraper',
    'ScraperUtilities',
    'GitHubScraper',
    'ThingiverseScraper',
    'RavelryScraper'
]

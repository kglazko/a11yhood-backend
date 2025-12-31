"""
Seed all data for local development.

This script runs all seed scripts in the correct order:
1. seed_supported_sources - Populates supported sources
2. seed_scraper_search_terms - Seeds scraper search terms
3. seed_test_users - Creates test users
4. seed_test_product - Creates test product
5. seed_test_collections - Creates test collections

Run with: uv run python seed_all.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
env_file = os.getenv('ENV_FILE', '.env.test')
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    logger.warning(f"Environment file {env_file} not found, using defaults")


def run_seed(script_name: str, module_name: str, function_name: str = 'main') -> bool:
    """Run a seed script and return success status."""
    try:
        logger.info(f"Running {script_name}...")
        
        # Import module and call the specified function
        module = __import__(module_name)
        if hasattr(module, function_name):
            getattr(module, function_name)()
        else:
            logger.error(f"  Function {function_name} not found in {module_name}")
            return False
        
        logger.info(f"✓ {script_name} completed successfully")
        return True
    except Exception as e:
        logger.error(f"✗ {script_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all seed scripts."""
    logger.info("=" * 60)
    logger.info("Starting database seeding process...")
    logger.info("=" * 60)
    
    seeds = [
        ("seed_supported_sources", "seed_supported_sources", "seed_supported_sources"),
        ("seed_oauth_configs", "seed_oauth_configs", "seed_oauth_configs"),
        ("seed_scraper_search_terms", "seed_scraper_search_terms", "main"),
        ("seed_test_users", "seed_test_users", "seed_users"),
        ("seed_test_product", "seed_test_product", "seed_product"),
        ("seed_test_collections", "seed_test_collections", "seed_collections"),
    ]
    
    results = {}
    for script_name, module_name, function_name in seeds:
        results[script_name] = run_seed(script_name, module_name, function_name)
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Seeding Summary:")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for script_name, success in results.items():
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{status}: {script_name}")
    
    logger.info("=" * 60)
    logger.info(f"Results: {passed}/{total} seed scripts completed successfully")
    logger.info("=" * 60)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

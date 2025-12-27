"""
Seed OAuth configs for scraper platforms (dev mode).

This script populates the oauth_configs table with platform configurations.
In test mode, this uses placeholder values; in production, OAuth configs must
be managed via admin UI or environment variables.

Run with: uv run python seed_oauth_configs.py
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_adapter import Base
import uuid

# Load environment variables
env_file = os.getenv('ENV_FILE', '.env.test')
if not os.path.exists(env_file):
    print(f"Warning: {env_file} not found, using defaults")
else:
    load_dotenv(env_file)

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("Error: DATABASE_URL not set")
    sys.exit(1)

# Create database engine and session
engine = create_engine(DATABASE_URL.replace('sqlite+aiosqlite', 'sqlite'), echo=False)
SessionLocal = sessionmaker(bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# OAuth configs for dev/test mode
# These are pre-seeded with minimal placeholder values.
# The frontend OAuth flow will update access_token/refresh_token when authorization completes.
# In production, these should be configured via the admin UI.
OAUTH_CONFIGS = [
    {
        "platform": "ravelry",
        "client_id": "PLACEHOLDER_CLIENT_ID",
        "client_secret": "PLACEHOLDER_CLIENT_SECRET",
        "redirect_uri": "http://localhost:8000/api/scrapers/oauth/ravelry/callback",
        "access_token": None,
        "refresh_token": None,
    },
    {
        "platform": "thingiverse",
        "client_id": "PLACEHOLDER_CLIENT_ID",
        "client_secret": "PLACEHOLDER_CLIENT_SECRET",
        "redirect_uri": "http://localhost:8000/api/scrapers/oauth/thingiverse/callback",
        "access_token": None,
        "refresh_token": None,
    },
    {
        "platform": "github",
        "client_id": "PLACEHOLDER_CLIENT_ID",
        "client_secret": "PLACEHOLDER_CLIENT_SECRET",
        "redirect_uri": "http://localhost:8000/api/auth/callback",
        "access_token": None,
        "refresh_token": None,
    },
]


def seed_oauth_configs():
    """Seed the oauth_configs table with platform configurations."""
    from database_adapter import OAuthConfig
    
    db = SessionLocal()
    try:
        print("Seeding oauth_configs table...")

        existing = {cfg.platform: cfg for cfg in db.query(OAuthConfig).all()}
        added = 0
        updated = 0

        for config_data in OAUTH_CONFIGS:
            platform = config_data["platform"]
            existing_config = existing.get(platform)

            if existing_config:
                # Update existing config
                existing_config.client_id = config_data["client_id"]
                existing_config.client_secret = config_data["client_secret"]
                existing_config.redirect_uri = config_data["redirect_uri"]
                if config_data.get("access_token"):
                    existing_config.access_token = config_data["access_token"]
                if config_data.get("refresh_token"):
                    existing_config.refresh_token = config_data["refresh_token"]
                updated += 1
            else:
                # Create new config
                config = OAuthConfig(
                    id=str(uuid.uuid4()),
                    platform=platform,
                    client_id=config_data["client_id"],
                    client_secret=config_data["client_secret"],
                    redirect_uri=config_data["redirect_uri"],
                    access_token=config_data.get("access_token"),
                    refresh_token=config_data.get("refresh_token"),
                )
                db.add(config)
                added += 1
                print(f"  Added: {platform}")

        db.commit()

        total = len(existing) + added
        print(f"✓ OAuth configs present: {total} (added {added}, updated {updated})")
    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding oauth_configs: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_oauth_configs()

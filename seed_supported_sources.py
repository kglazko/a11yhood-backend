#!/usr/bin/env python3
"""
Seed the supported_sources table with initial data.
This script can be run independently to populate the supported sources.

Run with: uv run python seed_supported_sources.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_adapter import SupportedSource, Base
import uuid

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_adapter import SupportedSource, Base
import uuid

# Load environment variables - prefer ENV_FILE if set, otherwise use .env.test
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

SUPPORTED_SOURCES = [
    {"domain": "ravelry.com", "name": "Ravelry"},
    {"domain": "github.com", "name": "Github"},
    {"domain": "thingiverse.com", "name": "Thingiverse"},
    {"domain": "example.com", "name": "Example"},
]


def seed_supported_sources():
    """Seed the supported_sources table with initial data."""
    db = SessionLocal()
    try:
        print("Seeding supported_sources table...")

        existing = {src.domain.lower(): src for src in db.query(SupportedSource).all()}
        added = 0
        updated = 0

        for source_data in SUPPORTED_SOURCES:
            domain = source_data["domain"].lower()
            name = source_data["name"]
            existing_source = existing.get(domain)

            if existing_source:
                if existing_source.name != name:
                    existing_source.name = name
                    updated += 1
            else:
                source = SupportedSource(
                    id=str(uuid.uuid4()),
                    domain=domain,
                    name=name,
                )
                db.add(source)
                added += 1
                print(f"  Added: {domain} ({name})")

        db.commit()

        total = len(existing) + added
        print(f"✓ Supported sources present: {total} (added {added}, updated {updated})")
    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding supported_sources: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_supported_sources()

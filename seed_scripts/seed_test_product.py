"""
Seed test product for local development

Creates one test product for testing

Run with: uv run python seed_test_product.py
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_adapter import Product, Tag, ProductTag, Base
from services.id_generator import normalize_to_snake_case
from datetime import datetime, UTC

# Load environment variables
load_dotenv('.env.test')

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')

# Create database engine and session
engine = create_engine(DATABASE_URL.replace('sqlite+aiosqlite', 'sqlite'), echo=False)
SessionLocal = sessionmaker(bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

def generate_slug(name: str, db_session) -> str:
    """Generate a unique slug from a product name"""
    base_slug = normalize_to_snake_case(name)
    
    # Check if base slug exists
    existing = db_session.query(Product).filter(Product.slug == base_slug).first()
    if not existing:
        return base_slug
    
    # If base slug exists, try appending numbers
    for i in range(1, 1000):
        candidate_slug = f"{base_slug}_{i}"
        existing = db_session.query(Product).filter(Product.slug == candidate_slug).first()
        if not existing:
            return candidate_slug
    
    # Fallback (should never reach here)
    import uuid
    return f"{base_slug}_{str(uuid.uuid4())[:8]}"

def seed_product():
    """Create test product in the database"""
    print("Creating test product...\n")
    
    db = SessionLocal()
    
    try:
        # Accessibility-focused test product aligned with frontend tests
        # Using github.com URL (one of the supported sources)
        product_name = "Test Product"
        tags = ["accessibility", "testing"]

        # Always generate a fresh slug and let the DB generate a UUID id
        slug = generate_slug(product_name, db)
        product = Product(
            name=product_name,
            url="https://github.com/test/product",
            type="Software",
            source="Github",  # Must match supported sources: Ravelry, Github, Thingiverse
            description="A test product for accessibility",
            slug=slug,
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            source_last_updated=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(product)
        db.commit()
        print(f"  ✓ Created product: {product_name} (ID: {product.id}, Slug: {slug})")

        # Attach tags (mirrors Supabase schema: tags + product_tags)
        for tag_name in tags:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.add(tag)
                db.commit()
                print(f"  ✓ Created tag: {tag_name}")
            link = ProductTag(product_id=product.id, tag_id=tag.id)
            db.add(link)
            db.commit()
        print(f"  ✓ Linked tags: {', '.join(tags)}")

        print("\n✓ Test product setup complete!")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_product()

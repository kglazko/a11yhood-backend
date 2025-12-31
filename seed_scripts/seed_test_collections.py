"""
Seed test collections for local development

Creates sample collections for testing and development:
1. Public collection with products (admin user)
2. Private collection (regular user)
3. Empty public collection (admin user)

Run with: uv run python seed_test_collections.py
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_adapter import Collection, Base
import uuid
from datetime import datetime, UTC

# Load environment variables
load_dotenv('.env.test')

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')

# Create database engine and session
engine = create_engine(DATABASE_URL.replace('sqlite+aiosqlite', 'sqlite'), echo=False)
SessionLocal = sessionmaker(bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Test collections data
test_collections = [
    {
        "id": "coll-admin-public-001",
        "user_id": "49366adb-2d13-412f-9ae5-4c35dbffab10",  # admin_user
        "user_name": "admin_user",
        "name": "Accessible Software Tools",
        "description": "A curated collection of software tools with excellent accessibility features",
        "product_ids": ["product1"],  # Will contain test product if it exists
        "is_public": True,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
        "updated_at": datetime.now(UTC).replace(tzinfo=None),
    },
    {
        "id": "coll-regular-private-001",
        "user_id": "f8f9fa4b-d03e-4a5c-85f5-4e6f3c9d7a2b",  # regular_user
        "user_name": "regular_user",
        "name": "My Personal Collection",
        "description": "Private collection of products I like",
        "product_ids": [],
        "is_public": False,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
        "updated_at": datetime.now(UTC).replace(tzinfo=None),
    },
    {
        "id": "coll-admin-public-002",
        "user_id": "49366adb-2d13-412f-9ae5-4c35dbffab10",  # admin_user
        "user_name": "admin_user",
        "name": "Empty Collection",
        "description": "A public collection waiting for products",
        "product_ids": [],
        "is_public": True,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
        "updated_at": datetime.now(UTC).replace(tzinfo=None),
    },
]

def seed_collections():
    """Create test collections in the database"""
    print("Creating test collections...\n")
    
    session = SessionLocal()
    
    try:
        for coll_data in test_collections:
            # Check if collection already exists
            existing = session.query(Collection).filter(Collection.id == coll_data["id"]).first()
            
            if existing:
                # Update existing collection
                for key, value in coll_data.items():
                    setattr(existing, key, value)
                session.commit()
                print(f"  ✓ Updated collection '{coll_data['name']}' (ID: {coll_data['id']})")
            else:
                # Create new collection
                collection = Collection(**coll_data)
                session.add(collection)
                session.commit()
                print(f"  ✓ Created collection '{coll_data['name']}' (ID: {coll_data['id']})")
        
        print("\n✓ Test collections setup complete!")
        
    except Exception as e:
        session.rollback()
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    seed_collections()

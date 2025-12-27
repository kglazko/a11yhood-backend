"""
Seed test users for local development

Creates three test users:
1. Admin user
2. Moderator user  
3. Regular user

Run with: uv run python seed_test_users.py
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database_adapter import User, Base
import uuid
from datetime import datetime

# Load environment variables
load_dotenv('.env.test')

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')

# Create database engine and session
engine = create_engine(DATABASE_URL.replace('sqlite+aiosqlite', 'sqlite'), echo=False)
SessionLocal = sessionmaker(bind=engine)

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Test users data (fixed IDs so resets keep roles stable in test mode)
test_users = [
    {
        "id": "49366adb-2d13-412f-9ae5-4c35dbffab10",  # matches DevAuthContext admin
        "github_id": "admin-test-001",
        "username": "admin_user",
        "display_name": "Admin User",
        "email": "admin@example.com",
        "role": "admin",
    },
    {
        "id": "94e116f7-885d-4d32-87ae-697c5dc09b9e",  # matches DevAuthContext moderator
        "github_id": "mod-test-002",
        "username": "moderator_user",
        "display_name": "Moderator User",
        "email": "moderator@example.com",
        "role": "moderator",
    },
    {
        "id": "2a3b7c3e-971b-4b42-9c8c-0f1843486c50",  # matches DevAuthContext regular user
        "github_id": "user-test-003",
        "username": "regular_user",
        "display_name": "Regular User",
        "email": "user@example.com",
        "role": "user",
    }
]

def seed_users():
    """Create test users in the database"""
    print(f"Using database: {DATABASE_URL}")
    print("Creating test users...\n")
    
    db = SessionLocal()
    
    try:
        for user_data in test_users:
            # Check by explicit ID first (to handle fixed IDs), then by github_id
            existing = db.query(User).filter(User.id == user_data["id"]).first()
            if not existing:
                existing = db.query(User).filter(User.github_id == user_data["github_id"]).first()

            if existing:
                print(f"  ✓ User {user_data['username']} ({user_data['role']}) already exists (ID: {existing.id})")
                # Update core fields and role to keep in sync with fixtures
                existing.github_id = user_data["github_id"]
                existing.username = user_data["username"]
                existing.display_name = user_data["display_name"]
                existing.email = user_data["email"]
                if getattr(existing, 'role', None) != user_data["role"]:
                    existing.role = user_data["role"]
                db.commit()
                print(f"    Ensured role={existing.role} and metadata is current")
            else:
                # Create new user with fixed ID
                new_user = User(
                    id=user_data["id"],
                    github_id=user_data["github_id"],
                    username=user_data["username"],
                    display_name=user_data["display_name"],
                    email=user_data["email"],
                    role=user_data["role"]
                )
                db.add(new_user)
                db.commit()
                
                print(f"  ✓ Created {user_data['role']}: {user_data['username']} (ID: {new_user.id})")
        
        print("\n✓ Test users setup complete!")
        print("\nTest Accounts:")
        print("-" * 70)
        print(f"{'Role':<12} | {'Username':<18} | {'Email':<25} | {'GitHub ID'}")
        print("-" * 70)
        for user in test_users:
            print(f"{user['role']:<12} | {user['username']:<18} | {user['email']:<25} | {user['github_id']}")
        print("-" * 70)
        print("\nNOTE: Users are identified by their 'role' field (admin, moderator, or user).")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()

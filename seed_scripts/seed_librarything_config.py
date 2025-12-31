#!/usr/bin/env python3
"""
Seed script to set up LibraryThing API configuration for GOAT (Gets Organized About Things)
Stores the API key needed for GOAT/LibraryThing book scraping

Usage:
    python seed_librarything_config.py --key YOUR_LIBRARYTHING_API_KEY
"""
import argparse
import os
from datetime import datetime, UTC
from services.database import init_supabase


def seed_librarything_config(api_key: str):
    """Add LibraryThing API configuration for GOAT to oauth_configs table"""
    supabase = init_supabase()
    
    if not api_key:
        print("❌ Error: API key is required")
        print("Get your key from: https://www.librarything.com/services/keys.php")
        return False
    
    try:
        # Check if already exists
        response = supabase.table("oauth_configs").select("*").eq("platform", "goat").execute()
        
        data = {
            "platform": "goat",
            "access_token": api_key,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        
        if response.data:
            # Update existing
            supabase.table("oauth_configs").update(data).eq("platform", "goat").execute()
            print(f"✅ Updated GOAT API configuration")
        else:
            # Create new
            supabase.table("oauth_configs").insert(data).execute()
            print(f"✅ Created GOAT API configuration")
        
        return True
    
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Set up LibraryThing API configuration for GOAT book scraping"
    )
    parser.add_argument(
        "--key",
        type=str,
        help="LibraryThing API key (get from https://www.librarything.com/services/keys.php)"
    )
    parser.add_argument(
        "--from-env",
        action="store_true",
        help="Read API key from LIBRARYTHING_API_KEY environment variable"
    )
    
    args = parser.parse_args()
    
    api_key = None
    
    if args.from_env:
        api_key = os.getenv("LIBRARYTHING_API_KEY")
        if not api_key:
            print("❌ Error: LIBRARYTHING_API_KEY environment variable not set")
            return 1
    elif args.key:
        api_key = args.key
    else:
        print("Usage: python seed_librarything_config.py --key YOUR_API_KEY")
        print("Or set LIBRARYTHING_API_KEY environment variable and use --from-env")
        return 1
    
    if seed_librarything_config(api_key):
        return 0
    else:
        return 1


if __name__ == "__main__":
    exit(main())

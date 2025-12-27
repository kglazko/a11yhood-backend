"""
Make a user an admin in the production database

Usage:
    uv run python make_admin.py <github_id>
    
Example:
    uv run python make_admin.py jmankoff
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

# Load production environment variables
load_dotenv('.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')  # Service role key with admin permissions

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    print("These should be your production Supabase credentials.")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: uv run python make_admin.py <github_username>")
    print("Example: uv run python make_admin.py jmankoff")
    sys.exit(1)

github_username = sys.argv[1]

# Create Supabase client with service role key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def make_admin(github_username: str):
    """Make a user an admin by their GitHub username"""
    print(f"Looking for user with GitHub username: {github_username}")
    
    try:
        # Find user by github username (stored in users table)
        result = supabase.table("users").select("*").eq("username", github_username).execute()
        
        if not result.data:
            print(f"✗ User '{github_username}' not found in users table.")
            print("\nNote: User must sign in at least once before being made admin.")
            print("After they sign in, their user record will be created automatically.")
            return False
        
        user = result.data[0]
        user_id = user['id']
        
        # Check if already admin
        if user.get('role') == 'admin':
            print(f"✓ User '{github_username}' is already an admin")
            return True
        
        # Update user to admin role
        update_result = supabase.table("users").update({
            "role": "admin"
        }).eq("id", user_id).execute()
        
        if update_result.data:
            print(f"✓ Successfully made '{github_username}' an admin!")
            print(f"  User ID: {user_id}")
            print(f"  Email: {user.get('email', 'N/A')}")
            return True
        else:
            print(f"✗ Failed to update user role")
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = make_admin(github_username)
    sys.exit(0 if success else 1)

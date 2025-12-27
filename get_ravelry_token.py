#!/usr/bin/env python3
"""
Helper script to get Ravelry OAuth access tokens

Ravelry uses OAuth 1.0a which requires a manual authorization flow.
This script walks you through the process.

Prerequisites:
1. Create a Ravelry app at https://www.ravelry.com/pro/developer
2. Have your API Key and API Secret ready

Usage:
    uv run python get_ravelry_token.py

The script will output tokens to add to your .env.test file.
"""

from requests_oauthlib import OAuth1Session
import sys


def get_ravelry_tokens():
    """Interactive OAuth 1.0a flow for Ravelry"""
    
    print("=" * 60)
    print("Ravelry OAuth Token Generator")
    print("=" * 60)
    print()
    print("You'll need your Ravelry API Key and API Secret.")
    print("Get them from: https://www.ravelry.com/pro/developer")
    print()
    
    # Get credentials
    client_key = input("Enter your Ravelry API Key: ").strip()
    if not client_key:
        print("Error: API Key is required")
        sys.exit(1)
    
    client_secret = input("Enter your Ravelry API Secret: ").strip()
    if not client_secret:
        print("Error: API Secret is required")
        sys.exit(1)
    
    print("\nStarting OAuth flow...\n")
    
    # OAuth endpoints
    request_token_url = 'https://www.ravelry.com/oauth/request_token'
    authorize_url = 'https://www.ravelry.com/oauth/authorize'
    access_token_url = 'https://www.ravelry.com/oauth/access_token'
    
    try:
        # Step 1: Get request token
        print("Step 1: Requesting temporary token...")
        # Use 'oob' (out-of-band) since Ravelry requires HTTPS for callbacks
        oauth = OAuth1Session(client_key, client_secret=client_secret, callback_uri='oob')
        fetch_response = oauth.fetch_request_token(request_token_url)
        resource_owner_key = fetch_response.get('oauth_token')
        resource_owner_secret = fetch_response.get('oauth_token_secret')
        print("✓ Got temporary token")
        
        # Step 2: Get authorization
        print("\nStep 2: User authorization required")
        authorization_url = oauth.authorization_url(authorize_url)
        print("-" * 60)
        print("Please visit this URL in your browser:")
        print(authorization_url)
        print("-" * 60)
        print()
        verifier = input("After authorizing, enter the verification code: ").strip()
        
        if not verifier:
            print("Error: Verification code is required")
            sys.exit(1)
        
        # Step 3: Get access token
        print("\nStep 3: Exchanging for access token...")
        oauth = OAuth1Session(
            client_key,
            client_secret=client_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=verifier
        )
        oauth_tokens = oauth.fetch_access_token(access_token_url)
        
        access_token = oauth_tokens.get('oauth_token')
        access_token_secret = oauth_tokens.get('oauth_token_secret')
        
        # Success!
        print("\n" + "=" * 60)
        print("✓ SUCCESS! OAuth tokens obtained")
        print("=" * 60)
        print("\nAdd these lines to your backend/.env.test file:\n")
        print(f"RAVELRY_ACCESS_TOKEN={access_token}")
        print(f"RAVELRY_ACCESS_TOKEN_SECRET={access_token_secret}")
        print(f"RAVELRY_CLIENT_ID={client_key}")
        print(f"RAVELRY_CLIENT_SECRET={client_secret}")
        print()
        print("Then run: uv run pytest tests/test_scrapers_integration.py -v")
        print()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Verify your API Key and Secret are correct")
        print("2. Make sure your Ravelry app redirect URI is set to:")
        print("   http://localhost:8000/api/scrapers/oauth/ravelry/callback")
        print("3. Check that you entered the verification code correctly")
        sys.exit(1)


if __name__ == "__main__":
    try:
        get_ravelry_tokens()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)

#!/usr/bin/env python3
"""
Debug script to test Ravelry API authentication

This script helps diagnose OAuth issues by testing different auth methods
and showing detailed error messages.
"""

import sys
import requests
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1Session
import json


def test_basic_auth(api_key, api_secret):
    """Test if Basic Auth works (for read-only endpoints)"""
    print("\n" + "="*60)
    print("Test 1: Basic Authentication")
    print("="*60)
    
    url = "https://api.ravelry.com/current_user.json"
    
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(api_key, api_secret),
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✓ Basic Auth works!")
            data = response.json()
            print(f"  User: {data.get('user', {}).get('username', 'Unknown')}")
            return True
        elif response.status_code == 401:
            print("✗ 401 Unauthorized - Invalid credentials")
            print(f"  Response: {response.text}")
        elif response.status_code == 403:
            print("✗ 403 Forbidden - App not authorized")
            print(f"  Response: {response.text}")
            print("\n  This usually means:")
            print("  1. Your app needs to be approved by Ravelry")
            print("  2. You need Pro membership to use the API")
            print("  3. Check your app status at: https://www.ravelry.com/pro/developer")
        else:
            print(f"✗ Unexpected status: {response.status_code}")
            print(f"  Response: {response.text}")
        
        return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_oauth1_flow(api_key, api_secret):
    """Test OAuth 1.0a flow with detailed output"""
    print("\n" + "="*60)
    print("Test 2: OAuth 1.0a Flow")
    print("="*60)
    
    request_token_url = 'https://www.ravelry.com/oauth/request_token'
    authorize_url = 'https://www.ravelry.com/oauth/authorize'
    access_token_url = 'https://www.ravelry.com/oauth/access_token'
    
    try:
        # Step 1: Request Token
        print("\nStep 1: Requesting temporary token...")
        oauth = OAuth1Session(api_key, client_secret=api_secret)
        
        try:
            fetch_response = oauth.fetch_request_token(request_token_url)
        except Exception as e:
            print(f"✗ Failed to get request token: {e}")
            if "401" in str(e):
                print("  401 error usually means invalid API key/secret")
            elif "403" in str(e):
                print("  403 error usually means app not approved")
            return False
        
        resource_owner_key = fetch_response.get('oauth_token')
        resource_owner_secret = fetch_response.get('oauth_token_secret')
        print(f"✓ Got request token: {resource_owner_key[:20]}...")
        
        # Step 2: User Authorization
        print("\nStep 2: User authorization")
        authorization_url = oauth.authorization_url(authorize_url)
        print("Visit this URL in your browser:")
        print("-" * 60)
        print(authorization_url)
        print("-" * 60)
        print("\nAfter authorizing, Ravelry will show a verification code.")
        print("The code is just plain text on the page (looks like a random string).")
        
        verifier = input("\nPaste the verification code here: ").strip()
        
        if not verifier:
            print("✗ No verification code provided")
            return False
        
        print(f"\nVerification code: {verifier}")
        
        # Step 3: Access Token
        print("\nStep 3: Exchanging for access token...")
        oauth = OAuth1Session(
            api_key,
            client_secret=api_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=verifier
        )
        
        try:
            oauth_tokens = oauth.fetch_access_token(access_token_url)
        except Exception as e:
            print(f"✗ Failed to get access token: {e}")
            print(f"\nDebug info:")
            print(f"  API Key: {api_key[:20]}...")
            print(f"  Request Token: {resource_owner_key}")
            print(f"  Verifier: {verifier}")
            
            if "401" in str(e):
                print("\n  Possible causes:")
                print("  - Verification code is incorrect or expired")
                print("  - App is not approved by Ravelry")
                print("  - API credentials don't match the app")
            
            return False
        
        access_token = oauth_tokens.get('oauth_token')
        access_token_secret = oauth_tokens.get('oauth_token_secret')
        
        print("✓ SUCCESS! Got access tokens:")
        print("\nAdd these to your .env.test file:")
        print("-" * 60)
        print(f"RAVELRY_ACCESS_TOKEN={access_token}")
        print(f"RAVELRY_ACCESS_TOKEN_SECRET={access_token_secret}")
        print(f"RAVELRY_APP_KEY={api_key}")
        print(f"RAVELRY_APP_SECRET={api_secret}")
        print("-" * 60)
        
        # Test the tokens
        print("\nTesting access tokens...")
        test_oauth = OAuth1Session(
            api_key,
            client_secret=api_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret
        )
        
        response = test_oauth.get('https://api.ravelry.com/current_user.json')
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Tokens work! User: {data.get('user', {}).get('username', 'Unknown')}")
        else:
            print(f"⚠ Tokens obtained but test failed: {response.status_code}")
            print(f"  Response: {response.text}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_app_status():
    """Instructions for checking app status"""
    print("\n" + "="*60)
    print("How to Check Your Ravelry App Status")
    print("="*60)
    print("""
1. Go to: https://www.ravelry.com/pro/developer
2. Find your app in the list
3. Check the status column:
   - "Approved" ✓ - App is ready to use
   - "Pending" ⏳ - Waiting for Ravelry approval (1-2 days)
   - "Denied" ✗ - App was rejected
   
4. If pending or denied:
   - Contact Ravelry support: help@ravelry.com
   - Explain you're building an accessibility tool
   - Reference their API docs: https://www.ravelry.com/api
   
5. Requirements:
   - Pro membership ($25/year)
   - Valid use case (accessibility scraping should qualify)
   - Proper app description
""")


def main():
    print("="*60)
    print("Ravelry API Authentication Debugger")
    print("="*60)
    
    # Get credentials
    api_key = input("\nEnter your Ravelry API Key: ").strip()
    if not api_key:
        print("Error: API Key is required")
        sys.exit(1)
    
    api_secret = input("Enter your Ravelry API Secret: ").strip()
    if not api_secret:
        print("Error: API Secret is required")
        sys.exit(1)
    
    # Test basic auth first
    basic_works = test_basic_auth(api_key, api_secret)
    
    if not basic_works:
        print("\n⚠ Basic Auth failed - your app may not be approved yet")
        check_app_status()
        
        print("\nDo you want to try the OAuth 1.0a flow anyway? (y/n): ", end="")
        if input().lower() != 'y':
            sys.exit(1)
    
    # Try OAuth flow
    oauth_works = test_oauth1_flow(api_key, api_secret)
    
    if oauth_works:
        print("\n" + "="*60)
        print("✓ SUCCESS! OAuth authentication working")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ OAuth authentication failed")
        print("="*60)
        check_app_status()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)

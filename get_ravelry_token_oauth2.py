#!/usr/bin/env python3
"""
Ravelry OAuth 2.0 Token Generator
Simple script to get Ravelry OAuth 2.0 access tokens for testing
"""

import sys
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import httpx


# Global variable to store the authorization code
authorization_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP server to receive OAuth callback"""
    
    def log_message(self, format, *args):
        """Suppress server logs"""
        pass
    
    def do_GET(self):
        global authorization_code
        
        # Parse the callback URL
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if 'code' in params:
            authorization_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    <script>window.close();</script>
                </body>
                </html>
            """)
        elif 'error' in params:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error_msg = params.get('error_description', [params['error'][0]])[0]
            self.wfile.write(f"""
                <html>
                <body>
                    <h1>Authorization Failed</h1>
                    <p>Error: {error_msg}</p>
                </body>
                </html>
            """.encode())
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Invalid callback")


def main():
    print("=" * 60)
    print("Ravelry OAuth 2.0 Token Generator")
    print("=" * 60)
    
    print("\nYou'll need your Ravelry Client ID and Client Secret.")
    print("Get them from: https://www.ravelry.com/pro/developer\n")
    
    # Get credentials
    client_id = input("Enter your Ravelry Client ID: ").strip()
    if not client_id:
        print("Error: Client ID is required")
        sys.exit(1)
    
    client_secret = input("Enter your Ravelry Client Secret: ").strip()
    if not client_secret:
        print("Error: Client Secret is required")
        sys.exit(1)
    
    # OAuth 2.0 endpoints
    authorize_url = 'https://www.ravelry.com/oauth2/auth'
    token_url = 'https://www.ravelry.com/oauth2/token'
    redirect_uri = 'http://localhost:8080/callback'
    
    print("\nStarting OAuth 2.0 flow...\n")
    print("Note: You'll need to add this redirect URI to your Ravelry app:")
    print(f"  {redirect_uri}")
    print("Visit: https://www.ravelry.com/pro/developer\n")
    
    # Step 1: Start local callback server
    print("Step 1: Starting local callback server...")
    server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    print("✓ Server listening on http://localhost:8080")
    
    # Step 2: Build authorization URL
    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'offline',  # Request offline access for refresh token
    }
    
    authorization_url = f"{authorize_url}?{urlencode(auth_params)}"
    
    print("\nStep 2: User authorization required")
    print("-" * 60)
    print("Opening browser for authorization...")
    
    # Try to open in browser
    try:
        webbrowser.open(authorization_url)
        print("✓ Opened in your default browser")
    except:
        print("⚠ Could not open browser automatically")
        print(f"Please visit: {authorization_url}")
    
    print("\nWaiting for authorization callback...")
    
    # Wait for callback
    global authorization_code
    import time
    timeout = 120  # 2 minutes
    elapsed = 0
    while authorization_code is None and elapsed < timeout:
        time.sleep(0.5)
        elapsed += 0.5
    
    server.shutdown()
    
    if authorization_code is None:
        print("\n✗ Timeout: No authorization code received")
        print("Please make sure you:")
        print("1. Added the redirect URI to your Ravelry app settings")
        print("2. Authorized the application in the browser")
        sys.exit(1)
    
    print(f"✓ Received authorization code")
    
    # Step 3: Exchange code for access token
    print("\nStep 3: Exchanging code for access token...")
    
    try:
        response = httpx.post(
            token_url,
            data={
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': redirect_uri,
                'client_id': client_id,
                'client_secret': client_secret,
            }
        )
        
        if response.status_code != 200:
            print(f"\n✗ Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 401:
                print("\nPossible causes:")
                print("- Authorization code is incorrect or expired")
                print("- Client ID or Secret is incorrect")
                print("- App is not approved")
            
            sys.exit(1)
        
        token_data = response.json()
        
        print("\n" + "=" * 60)
        print("✓ SUCCESS! OAuth 2.0 tokens obtained")
        print("=" * 60)
        
        print("\nAdd these lines to your backend/.env.test file:")
        print("-" * 60)
        print(f"RAVELRY_CLIENT_ID={client_id}")
        print(f"RAVELRY_CLIENT_SECRET={client_secret}")
        print(f"RAVELRY_ACCESS_TOKEN={token_data.get('access_token')}")
        if token_data.get('refresh_token'):
            print(f"RAVELRY_REFRESH_TOKEN={token_data.get('refresh_token')}")
        print("-" * 60)
        
        # Test the token
        print("\nTesting access token...")
        test_response = httpx.get(
            'https://api.ravelry.com/current_user.json',
            headers={'Authorization': f"Bearer {token_data.get('access_token')}"}
        )
        
        if test_response.status_code == 200:
            user_data = test_response.json()
            username = user_data.get('user', {}).get('username', 'Unknown')
            print(f"✓ Token works! Authenticated as: {username}")
        else:
            print(f"⚠ Token test failed: {test_response.status_code}")
            print(f"Response: {test_response.text}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)

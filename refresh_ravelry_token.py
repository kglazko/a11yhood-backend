"""Test and refresh Ravelry OAuth token"""
import httpx
import asyncio
import os
from supabase import create_client
from datetime import datetime, timedelta


async def refresh_ravelry_token():
    """Refresh the Ravelry OAuth token"""
    # Get current config from database
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    result = client.table("oauth_configs").select("*").eq("platform", "ravelry").execute()
    config = result.data[0]
    
    print(f"Current access token: {config['access_token'][:30]}...")
    print(f"Refresh token: {config['refresh_token'][:30]}...")
    
    # Refresh the token
    print("\nRefreshing token...")
    async with httpx.AsyncClient() as http_client:
        # Ravelry requires HTTP Basic Auth with client_id:client_secret
        response = await http_client.post(
            'https://www.ravelry.com/oauth2/token',
            auth=(config['client_id'], config['client_secret']),
            data={
                'grant_type': 'refresh_token',
                'refresh_token': config['refresh_token'],
            }
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to refresh token: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        token_data = response.json()
        print(f"✅ Token refreshed successfully!")
        print(f"New access token: {token_data['access_token'][:30]}...")
        
        # Update database
        update_data = {
            'access_token': token_data['access_token'],
            'updated_at': datetime.utcnow().isoformat(),
        }
        
        if 'refresh_token' in token_data:
            update_data['refresh_token'] = token_data['refresh_token']
            print(f"New refresh token: {token_data['refresh_token'][:30]}...")
        
        if 'expires_in' in token_data:
            expires_at = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
            update_data['token_expires_at'] = expires_at.isoformat()
            print(f"Token expires at: {expires_at}")
        
        client.table("oauth_configs").update(update_data).eq("platform", "ravelry").execute()
        print("✅ Database updated!")
        
        # Test the new token
        print("\nTesting new token...")
        headers = {"Authorization": f"Bearer {token_data['access_token']}", "Accept": "application/json"}
        test_response = await http_client.get(
            "https://api.ravelry.com/current_user.json",
            headers=headers
        )
        
        if test_response.status_code == 200:
            user = test_response.json().get("user", {})
            print(f"✅ Token works! User: {user.get('username')}")
        else:
            print(f"❌ Token test failed: {test_response.status_code}")


if __name__ == "__main__":
    asyncio.run(refresh_ravelry_token())

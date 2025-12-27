"""
Live scraper tests against a running backend, using saved DB credentials.

These tests hit the HTTP API so they can use whatever credentials are
stored in your database (oauth_configs). They require a running server.

Enable with:
  RUN_LIVE_SCRAPERS=1 RUN_AGAINST_SERVER=1 BACKEND_BASE_URL=http://localhost:8000 \
  DEV_USER_ID=<admin_user_id> pytest tests/test_scrapers_live_api.py -v

Alternatively, set ADMIN_TOKEN for real auth:
  RUN_LIVE_SCRAPERS=1 RUN_AGAINST_SERVER=1 BACKEND_BASE_URL=http://localhost:8000 \
  ADMIN_TOKEN=<jwt> pytest tests/test_scrapers_live_api.py -v

Notes:
- Requires backend TEST_MODE for dev-token path, or a valid admin JWT.
- Uses /api/scrapers/trigger which pulls tokens from oauth_configs.
"""
import os
import time
import pytest
import httpx

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

if not os.getenv("RUN_LIVE_SCRAPERS") or not os.getenv("RUN_AGAINST_SERVER"):
    pytest.skip("Skipping live API tests without RUN_LIVE_SCRAPERS=1 and RUN_AGAINST_SERVER=1", allow_module_level=True)


def _auth_headers():
    headers = {"Content-Type": "application/json"}
    admin_token = os.getenv("ADMIN_TOKEN")
    dev_user_id = os.getenv("DEV_USER_ID")
    if admin_token:
        headers["Authorization"] = f"Bearer {admin_token}"
    elif dev_user_id:
        headers["Authorization"] = f"dev-token-{dev_user_id}"
    else:
        # Try to create a temporary admin in TEST_MODE using dev-token
        temp_id = "live-admin-temp-0001"
        # Create user account (no auth required)
        import requests
        put_resp = requests.put(f"{BACKEND_BASE_URL}/api/users/{temp_id}", json={
            "username": "live_admin",
            "email": "live_admin@example.com"
        })
        if put_resp.status_code not in (200, 201):
            pytest.skip("Could not create temp user and no admin token provided")
        # Promote self with dev-token
        patch_resp = requests.patch(
            f"{BACKEND_BASE_URL}/api/users/{temp_id}/role",
            json={"role": "admin"},
            headers={"Authorization": f"dev-token-{temp_id}", "Content-Type": "application/json"}
        )
        if patch_resp.status_code != 200:
            pytest.skip("Could not promote temp admin and no admin token provided")
        headers["Authorization"] = f"dev-token-{temp_id}"
    return headers


async def _has_token(client: httpx.AsyncClient, platform: str, headers: dict) -> bool:
    resp = await client.get(f"{BACKEND_BASE_URL}/api/scrapers/oauth/{platform}/config", headers=headers)
    if resp.status_code != 200:
        return False
    data = resp.json()
    return bool(data.get("has_access_token"))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scrape_thingiverse_via_api():
    headers = _auth_headers()
    async with httpx.AsyncClient(timeout=120.0) as client:
        if not await _has_token(client, "thingiverse", headers):
            pytest.skip("No saved Thingiverse token in DB")
        # Trigger real run
        resp = await client.post(f"{BACKEND_BASE_URL}/api/scrapers/trigger", json={
            "source": "thingiverse",
            "test_mode": False
        }, headers=headers)
        assert resp.status_code == 200
        # Poll for products
        found = False
        for _ in range(20):
            time.sleep(3)
            pr = await client.get(f"{BACKEND_BASE_URL}/api/products", params={"origin": "scraped-thingiverse", "limit": 1}, headers=headers)
            if pr.status_code == 200 and isinstance(pr.json(), list) and len(pr.json()) > 0:
                found = True
                break
        assert found, "Expected Thingiverse products after trigger"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_scrape_ravelry_via_api():
    headers = _auth_headers()
    async with httpx.AsyncClient(timeout=120.0) as client:
        if not await _has_token(client, "ravelry", headers):
            pytest.skip("No saved Ravelry token in DB")
        # Trigger real run
        resp = await client.post(f"{BACKEND_BASE_URL}/api/scrapers/trigger", json={
            "source": "ravelry",
            "test_mode": False
        }, headers=headers)
        assert resp.status_code == 200
        # Poll for products
        found = False
        for _ in range(20):
            time.sleep(3)
            pr = await client.get(f"{BACKEND_BASE_URL}/api/products", params={"origin": "scraped-ravelry", "limit": 1}, headers=headers)
            if pr.status_code == 200 and isinstance(pr.json(), list) and len(pr.json()) > 0:
                found = True
                break
        assert found, "Expected Ravelry products after trigger"

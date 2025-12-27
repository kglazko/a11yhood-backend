import os
os.environ.setdefault("ENV_FILE", "backend/.env.test")
try:
    from dotenv import load_dotenv
    load_dotenv(os.environ["ENV_FILE"])
except Exception:
    pass

import pytest
from fastapi.testclient import TestClient
from main import app
from services.database import get_db
from services.auth import get_current_user
from .test_data import TEST_PRODUCTS, TEST_USERS
from datetime import UTC


@pytest.fixture
def client(clean_database):
    """Test client using SQLite. Auth is driven by Authorization headers."""
    app.dependency_overrides[get_db] = lambda: clean_database
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(clean_database, test_user):
    """Test client authenticated as regular user via Authorization header."""
    from main import app
    app.dependency_overrides[get_db] = lambda: clean_database
    base_client = TestClient(app)

    class _AuthClient:
        def __init__(self, base, user):
            self._base = base
            self._headers = {"Authorization": f"dev-token-{user['id']}"}

        def request(self, method, url, **kwargs):
            headers = kwargs.pop("headers", {}) or {}
            merged = {**self._headers, **headers}
            return self._base.request(method, url, headers=merged, **kwargs)

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

        def put(self, url, **kwargs):
            return self.request("PUT", url, **kwargs)

        def patch(self, url, **kwargs):
            return self.request("PATCH", url, **kwargs)

        def delete(self, url, **kwargs):
            return self.request("DELETE", url, **kwargs)

    client = _AuthClient(base_client, test_user)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def admin_client(clean_database, test_admin):
    """Test client authenticated as admin user via Authorization header."""
    from main import app
    app.dependency_overrides[get_db] = lambda: clean_database
    base_client = TestClient(app)

    class _AuthClient:
        def __init__(self, base, user):
            self._base = base
            self._headers = {"Authorization": f"dev-token-{user['id']}"}

        def request(self, method, url, **kwargs):
            headers = kwargs.pop("headers", {}) or {}
            merged = {**self._headers, **headers}
            return self._base.request(method, url, headers=merged, **kwargs)

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

        def put(self, url, **kwargs):
            return self.request("PUT", url, **kwargs)

        def patch(self, url, **kwargs):
            return self.request("PATCH", url, **kwargs)

        def delete(self, url, **kwargs):
            return self.request("DELETE", url, **kwargs)

    client = _AuthClient(base_client, test_admin)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth_client_2(clean_database, test_user_2):
    """Test client authenticated as second test user via Authorization header."""
    from main import app
    app.dependency_overrides[get_db] = lambda: clean_database
    base_client = TestClient(app)

    class _AuthClient:
        def __init__(self, base, user):
            self._base = base
            self._headers = {"Authorization": f"dev-token-{user['id']}"}

        def request(self, method, url, **kwargs):
            headers = kwargs.pop("headers", {}) or {}
            merged = {**self._headers, **headers}
            return self._base.request(method, url, headers=merged, **kwargs)

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

        def put(self, url, **kwargs):
            return self.request("PUT", url, **kwargs)

        def patch(self, url, **kwargs):
            return self.request("PATCH", url, **kwargs)

        def delete(self, url, **kwargs):
            return self.request("DELETE", url, **kwargs)

    client = _AuthClient(base_client, test_user_2)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


# ============================================================================
# Integration test fixtures (SQLite) - for test_scrapers_integration.py
# ============================================================================

import os
from database_adapter import DatabaseAdapter
from config import get_settings


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(test_settings):
    """
    Session-scoped fixture that ensures test database starts clean.
    
    This runs once at the start of all tests and clears any stale data
    from previous test runs, ensuring frontend and backend tests use
    the same clean slate.
    """
    test_db = DatabaseAdapter(test_settings)
    test_db.init()  # Create tables
    test_db.cleanup()  # Drop and recreate tables to start fresh
    print("\n✓ Test database reset at session start")


@pytest.fixture(scope="session")
def test_settings():
    """Load test environment settings from ENV_FILE (defaults to backend/.env.test)."""
    return get_settings(os.environ.get("ENV_FILE", "backend/.env.test"))


@pytest.fixture(scope="session")
def test_db(test_settings):
    """SQLite database for testing (no Supabase required)"""
    db = DatabaseAdapter(test_settings)
    db.init()  # Create tables
    yield db
    # Cleanup happens per test


@pytest.fixture
def clean_database(test_db):
    """Clean database before each test"""
    test_db.cleanup()  # Drop and recreate tables
    # Seed test data fresh for each test
    _seed_test_data(test_db)
    yield test_db


def _seed_test_data(db):
    """
    Seed initial test data using shared constants.
    
    This ensures consistency between backend tests and frontend integration tests.
    All products use controlled types/sources from test_data.py.
    """
    from uuid import uuid4
    from datetime import datetime
    
    # Create supported sources for URL validation
    supported_sources = [
        {
            "domain": "ravelry.com",
            "name": "Ravelry",
        },
        {
            "domain": "github.com",
            "name": "Github",
        },
        {
            "domain": "thingiverse.com",
            "name": "Thingiverse",
        },
    ]
    
    try:
        for source in supported_sources:
            db.table("supported_sources").insert(source).execute()
    except Exception:
        pass  # Sources may already exist
    
    # Create test users with unique IDs so no conflicts
    test_users = [
        {
            "id": str(uuid4()),
            "github_id": f"test-user-{uuid4()}",
            "username": "testuser",
            "email": "test@example.com",
            "display_name": "Test User",
            "role": "user",
            "created_at": datetime.now(UTC).isoformat(),
        },
        {
            "id": str(uuid4()),
            "github_id": f"test-admin-{uuid4()}",
            "username": "testadmin",
            "email": "admin@example.com",
            "display_name": "Test Admin",
            "role": "admin",
            "created_at": datetime.now(UTC).isoformat(),
        },
    ]
    
    try:
        for user in test_users:
            db.table("users").insert(user).execute()
    except Exception:
        pass  # Users may already exist
    
    # Create test products from shared constants
    try:
        for product in TEST_PRODUCTS:
            db.table("products").insert(product).execute()
    except Exception:
        pass  # Products may already exist


@pytest.fixture
def test_user(clean_database):
    """Create a test user in the test database"""
    from uuid import uuid4
    user_data = {
        "id": str(uuid4()),
        "github_id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "display_name": "Test User",
        "role": "user",
    }

    result = clean_database.table("users").insert(user_data).execute()
    return result.data[0]


@pytest.fixture
def test_admin(clean_database):
    """Create a test admin user in the test database"""
    from uuid import uuid4
    admin_data = {
        "id": str(uuid4()),
        "github_id": "test-admin-456",
        "username": "testadmin",
        "email": "admin@example.com",
        "display_name": "Test Admin",
        "role": "admin",
    }

    result = clean_database.table("users").insert(admin_data).execute()
    return result.data[0]


@pytest.fixture
def test_moderator(clean_database):
    """Create a test moderator user in the test database"""
    from uuid import uuid4
    moderator_data = {
        "id": str(uuid4()),
        "github_id": "test-moderator-567",
        "username": "testmoderator",
        "email": "moderator@example.com",
        "display_name": "Test Moderator",
        "role": "moderator",
    }

    result = clean_database.table("users").insert(moderator_data).execute()
    return result.data[0]


@pytest.fixture
def test_user_2(clean_database):
    """Create a second test user in the test database"""
    from uuid import uuid4
    user_data = {
        "id": str(uuid4()),
        "github_id": "test-user-789",
        "username": "testuser2",
        "email": "test2@example.com",
        "display_name": "Test User 2",
        "role": "user",
    }

    result = clean_database.table("users").insert(user_data).execute()
    return result.data[0]


@pytest.fixture
def test_product(clean_database, test_user):
    """Create a test product owned by the test user"""
    from uuid import uuid4

    product_data = {
        "name": "Test Product",
        "description": "A test product for testing",
        "source": "github",
        "category": "Software",
        "url": f"https://github.com/test/test-product-{uuid4()}",
        "created_by": test_user["id"],
    }

    result = clean_database.table("products").insert(product_data).execute()
    return result.data[0]


@pytest.fixture
def sqlite_db(clean_database):
    """Alias for clean_database fixture for clearer test code"""
    return clean_database


@pytest.fixture
def auth_headers():
    """Return a factory that builds dev-token Authorization headers for a given user dict."""
    def _make(user: dict):
        return {"Authorization": f"dev-token-{user['id']}"}
    return _make


# Removed duplicate auth_headers that overrode dependencies; we standardize on header-based tokens.


@pytest.fixture
def github_oauth_config(clean_database, test_admin):
    """Create GitHub OAuth config (no actual credentials needed for public API)"""
    config_data = {
        "platform": "github",
        "client_id": "test-client-id",
        "client_secret": "test-secret",
        "redirect_uri": "http://localhost:8000/api/scrapers/oauth/github/callback"
    }
    
    result = clean_database.table("oauth_configs").insert(config_data).execute()
    return result.data[0]


@pytest.fixture
def thingiverse_oauth_config(clean_database, test_admin, test_settings):
    """
    Create Thingiverse OAuth config with access token
    
    Note: This fixture requires real credentials to work.
    Set THINGIVERSE_APP_ID in .env.test or skip tests.
    """
    access_token = test_settings.THINGIVERSE_APP_ID
    
    if not access_token:
        pytest.skip("THINGIVERSE_APP_ID not set in .env.test")
    
    config_data = {
        "platform": "thingiverse",
        "client_id": access_token,  # Thingiverse uses app_id as access token
        "client_secret": "test-secret",
        "redirect_uri": "http://localhost:8000/api/scrapers/oauth/thingiverse/callback",
        "access_token": access_token
    }
    
    result = clean_database.table("oauth_configs").insert(config_data).execute()
    return result.data[0]


@pytest.fixture
def ravelry_oauth_config(clean_database, test_admin, test_settings):
    """
    Create Ravelry OAuth config with access token
    
    Note: This fixture requires real credentials to work.
    Set RAVELRY_APP_KEY and RAVELRY_APP_SECRET in .env.test or skip tests.
    """
    app_key = test_settings.RAVELRY_APP_KEY
    app_secret = test_settings.RAVELRY_APP_SECRET
    
    if not app_key or not app_secret:
        pytest.skip("RAVELRY_APP_KEY or RAVELRY_APP_SECRET not set in .env.test")
    
    config_data = {
        "platform": "ravelry",
        "client_id": app_key,
        "client_secret": app_secret,
        "redirect_uri": "http://localhost:8000/api/scrapers/oauth/ravelry/callback",
        "access_token": app_key  # For basic auth, use app_key as token
    }
    
    result = clean_database.table("oauth_configs").insert(config_data).execute()
    return result.data[0]

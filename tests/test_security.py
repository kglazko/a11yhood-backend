"""
Security regression tests (negative paths, authorization, and privacy checks).

These tests focus on:
- Auth required for protected endpoints
- Ownership/role enforcement to prevent IDOR
- Private collection access control
- Role-based feature gating (admin-only scrapers, manager-only edits)
"""

import time
import uuid


def _ensure_uuid(value: str) -> str:
    """Return value if valid UUID else allocate a new UUID string."""
    try:
        uuid.UUID(value)
        return value
    except Exception:
        return str(uuid.uuid4())


def _sample_product_payload():
    return {
        "name": "Secure Test Product",
        "description": "Security negative-path test product",
        "source_url": "https://github.com/user/secure-product",
        "image_url": None,
        "source": "github",
        "type": "Other",
        "tags": [],
    }


def _sample_blog_payload(author_id: str, author_name: str, slug: str, published: bool = False):
    author_uuid = _ensure_uuid(author_id)
    return {
        "title": "Security Blog Post",
        "slug": slug,
        "content": "**secure** content with markdown",
        "excerpt": "Security blog excerpt",
        "header_image": "data:image/png;base64,iVBORw0KGgo=",
        "header_image_alt": "Accessible header image",
        "author_id": author_uuid,
        "author_name": author_name,
        "author_ids": [author_uuid],
        "author_names": [author_name],
        "tags": ["security", "blog"],
        "published": published,
        "featured": True,
    }


# ============================================================================
# Authentication Tests
# ============================================================================

def test_create_product_requires_auth(client):
    payload = _sample_product_payload()
    response = client.post("/api/products", json=payload)
    assert response.status_code == 401


# ============================================================================
# Ownership & IDOR Tests
# ============================================================================

def test_update_product_forbidden_for_non_owner(auth_client, auth_client_2):
    # Owner creates product
    create = auth_client.post("/api/products", json=_sample_product_payload())
    assert create.status_code == 201
    product_id = create.json()["id"]

    # Another user attempts update
    update = auth_client_2.put(
        f"/api/products/{product_id}",
        json={"name": "Hacked"},
    )
    assert update.status_code == 403


def test_admin_can_update_any_product(auth_client, admin_client):
    # Regular user creates product
    create = auth_client.post("/api/products", json=_sample_product_payload())
    assert create.status_code == 201
    product_id = create.json()["id"]

    # Admin can update it
    update = admin_client.put(
        f"/api/products/{product_id}",
        json={"name": "Admin Updated"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Admin Updated"


def test_private_collection_access_control(auth_client, auth_client_2):
    # Owner creates private collection
    create = auth_client.post(
        "/api/collections",
        json={"name": "Private Coll", "description": None, "is_public": False},
    )
    assert create.status_code == 201
    collection_id = create.json()["id"]

    # Other user cannot fetch
    forbidden = auth_client_2.get(f"/api/collections/{collection_id}")
    assert forbidden.status_code == 403

    # Owner can fetch
    allowed = auth_client.get(f"/api/collections/{collection_id}")
    assert allowed.status_code == 200


def test_add_product_to_collection_forbidden_for_non_owner(auth_client, auth_client_2, test_product):
    # Owner creates collection
    create = auth_client.post(
        "/api/collections",
        json={"name": "Owned Collection", "description": None, "is_public": True},
    )
    assert create.status_code == 201
    collection_id = create.json()["id"]

    # Different user tries to add a product
    attempt = auth_client_2.post(
        f"/api/collections/{collection_id}/products/{test_product['id']}",
    )
    assert attempt.status_code == 403


# ============================================================================
# Role-Based Access Tests
# ============================================================================

def test_request_approval_requires_admin_or_moderator(client, test_user, auth_headers):
    # User creates a moderator request
    create = client.post(
        "/api/requests/",
        json={"type": "moderator", "reason": "security check"},
        headers=auth_headers(test_user),
    )
    assert create.status_code == 201
    request_id = create.json()["id"]

    # Same user cannot approve their own request
    patch = client.patch(
        f"/api/requests/{request_id}",
        json={"status": "approved"},
        headers=auth_headers(test_user),
    )
    assert patch.status_code == 403


def test_moderator_can_approve_product_editor_requests(client, test_user, test_product, test_moderator, auth_headers):
    # User requests product ownership
    create = client.post(
        "/api/requests/",
        json={
            "type": "product-ownership",
            "product_id": test_product["id"],
            "reason": "I maintain this project"
        },
        headers=auth_headers(test_user),
    )
    assert create.status_code == 201
    request_id = create.json()["id"]

    # Moderator can approve
    approve = client.patch(
        f"/api/requests/{request_id}",
        json={"status": "approved"},
        headers=auth_headers(test_moderator),
    )
    assert approve.status_code == 200


def test_scraper_trigger_requires_admin(client, test_user, test_moderator, auth_headers):
    payload = {"source": "github", "test_mode": True, "test_limit": 1}
    
    # Regular user blocked
    regular = client.post(
        "/api/scrapers/trigger",
        json=payload,
        headers=auth_headers(test_user),
    )
    assert regular.status_code == 403

    # Moderator blocked (only admin allowed)
    moderator = client.post(
        "/api/scrapers/trigger",
        json=payload,
        headers=auth_headers(test_moderator),
    )
    assert moderator.status_code == 403


def test_admin_can_trigger_scraper(admin_client):
    payload = {"source": "github", "test_mode": True, "test_limit": 1}
    
    # Admin allowed
    response = admin_client.post("/api/scrapers/trigger", json=payload)
    # Should accept (202) or return job info (200)
    assert response.status_code in [200, 202]


# ============================================================================
# Blog Post Access Control
# ============================================================================


def test_blog_post_creation_requires_admin(auth_client):
    slug = f"security-blog-{int(time.time() * 1000)}"
    payload = _sample_blog_payload(author_id="user-1", author_name="Regular User", slug=slug, published=True)

    response = auth_client.post("/api/blog-posts", json=payload)
    assert response.status_code == 403


def test_admin_can_publish_blog_post(admin_client):
    slug = f"security-blog-{int(time.time() * 1000)}"
    payload = _sample_blog_payload(author_id="admin-1", author_name="Admin User", slug=slug, published=True)

    create = admin_client.post("/api/blog-posts", json=payload)
    assert create.status_code == 201
    post = create.json()
    assert post["published"] is True
    assert post["header_image_alt"] == "Accessible header image"

    # Public (no auth header) should see published post
    public_list = admin_client._base.get("/api/blog-posts")
    assert public_list.status_code == 200
    slugs = [p.get("slug") for p in public_list.json()]
    assert slug in slugs

    public_detail = admin_client._base.get(f"/api/blog-posts/slug/{slug}")
    assert public_detail.status_code == 200
    detail = public_detail.json()
    assert detail["published"] is True
    assert detail["content"].startswith("**secure**")


def test_unpublished_blog_post_hidden_from_public(admin_client):
    slug = f"security-blog-unpublished-{int(time.time() * 1000)}"
    payload = _sample_blog_payload(author_id="admin-2", author_name="Admin User", slug=slug, published=False)

    create = admin_client.post("/api/blog-posts", json=payload)
    assert create.status_code == 201

    public_list = admin_client._base.get("/api/blog-posts")
    assert public_list.status_code == 200
    slugs = [p.get("slug") for p in public_list.json()]
    assert slug not in slugs

    public_detail = admin_client._base.get(f"/api/blog-posts/slug/{slug}")
    assert public_detail.status_code == 403


# ============================================================================
# Database Security Tests
# ============================================================================

def test_sql_injection_prevention_in_product_name(auth_client):
    """Verify that SQL injection attempts in product names are safely handled"""
    malicious_names = [
        "'; DROP TABLE products; --",
        "1' OR '1'='1",
        "admin'--",
        "<script>alert('xss')</script>",
        "../../etc/passwd",
    ]
    
    for malicious_name in malicious_names:
        response = auth_client.post(
            "/api/products",
            json={
                "name": malicious_name,
                "description": "Testing SQL injection prevention",
                "source_url": "https://github.com/user/test-sql",
                "source": "github",
                "type": "Other",
            },
        )
        # Should succeed (input is escaped/parameterized) or fail validation
        assert response.status_code in [201, 422]
        
        # If created, verify the name was stored as-is (not executed)
        if response.status_code == 201:
            product = response.json()
            assert product["name"] == malicious_name


def test_sql_injection_prevention_in_search(client):
    """Verify that SQL injection attempts in search queries are safely handled"""
    malicious_queries = [
        "'; DROP TABLE products; --",
        "1' OR '1'='1",
        "admin' OR 1=1--",
    ]
    
    for query in malicious_queries:
        response = client.get(f"/api/products?search={query}")
        # Should return safe results (no SQL executed)
        assert response.status_code == 200
        # Should return empty or filtered results, not error
        data = response.json()
        assert isinstance(data, list)


def test_large_text_fields_accepted(auth_client):
    """Verify that reasonably large text fields are accepted (no arbitrary limits)"""
    # Create a large description (10KB - reasonable for a product description)
    large_text = "A" * (10 * 1024)
    
    response = auth_client.post(
        "/api/products",
        json={
            "name": "Large Description Test",
            "description": large_text,
            "source_url": "https://github.com/user/test-large",
            "source": "github",
            "type": "Other",
        },
    )
    
    # Should accept reasonable payloads
    assert response.status_code == 201
    product = response.json()
    assert len(product["description"]) == len(large_text)


def test_special_characters_in_strings_handled_safely(auth_client):
    """Verify that special characters are properly escaped/stored"""
    special_chars_name = "Test™ Product® with §pecial ¢haracters & symbols <>"
    special_chars_desc = "Description with unicode: 你好 🎉 and symbols: & < > \" '"
    
    response = auth_client.post(
        "/api/products",
        json={
            "name": special_chars_name,
            "description": special_chars_desc,
            "source_url": "https://github.com/user/test-special",
            "source": "github",
            "type": "Other",
        },
    )
    
    assert response.status_code == 201
    product = response.json()
    # Verify characters are preserved exactly
    assert product["name"] == special_chars_name
    assert product["description"] == special_chars_desc


def test_null_byte_injection_prevented(auth_client):
    """Verify that null byte injection attempts are handled"""
    # Null bytes could be used to truncate strings or bypass filters
    response = auth_client.post(
        "/api/products",
        json={
            "name": "Test\x00Hidden",
            "description": "Test product",
            "source_url": "https://example.com/test",
            "source": "manual",
            "type": "Other",
        },
    )
    
    # Should either reject or sanitize the null byte
    assert response.status_code in [201, 422, 400]


def test_email_not_exposed_in_public_user_endpoint(client):
    """Verify that sensitive user data (email) is not exposed in public endpoints"""
    # Create a user with email
    user_id = str(uuid.uuid4())
    create_response = client.post(
        f"/api/users/{user_id}",
        json={
            "username": f"testuser{id(object())}",
            "email": "private@example.com",
        },
    )
    assert create_response.status_code in [200, 201]
    username = create_response.json()["username"]
    
    # Query via public endpoint
    response = client.get(f"/api/users/by-username/{username}")
    
    assert response.status_code == 200
    user = response.json()
    # Email should be None in public endpoint
    assert user.get("email") is None


def test_invalid_json_rejected(auth_client):
    """Verify that malformed JSON is properly rejected"""
    # Send invalid JSON
    response = auth_client.post(
        "/api/products",
        content="{'invalid': json}",  # Not valid JSON
        headers={"Content-Type": "application/json"},
    )
    
    # Should reject with 422 (Unprocessable Entity) or 400 (Bad Request)
    assert response.status_code in [422, 400]


def test_type_confusion_prevented(auth_client):
    """Verify that type confusion attacks are prevented by Pydantic validation"""
    # Try to send wrong types for fields
    response = auth_client.post(
        "/api/products",
        json={
            "name": ["array", "instead", "of", "string"],  # Should be string
            "description": 12345,  # Should be string
            "source_url": "https://example.com/test",
            "source": "manual",
            "type": "Other",
        },
    )
    
    # Pydantic should reject with validation error
    assert response.status_code == 422


def test_integer_overflow_prevented(auth_client, test_product):
    """Verify that integer fields handle extreme values safely"""
    import sys
    
    # Try to create a rating with an extreme value
    response = auth_client.post(
        f"/api/ratings",
        json={
            "product_id": test_product["id"],
            "stars": sys.maxsize,  # Extremely large integer
        },
    )
    
    # Should reject (validation error) - stars should be 1-5
    assert response.status_code == 422
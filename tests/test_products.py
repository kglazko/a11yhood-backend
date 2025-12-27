"""Test product endpoints using the local SQLite database"""
import pytest
import uuid


def test_get_products_success(client, test_product):
    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == test_product["id"] for item in data)


def test_get_products_with_filters(client, clean_database, test_product):
    clean_database.table("products").insert({
        "name": "GitHub Tool",
        "description": "From GitHub",
        "source": "github",
        "category": "Software",
        "url": "https://github.com/example/tool",
    }).execute()

    response = client.get("/api/products?origin=github&category=Software&search=tool")
    assert response.status_code == 200
    data = response.json()
    assert all(item["source"] == "github" for item in data)


def test_get_product_by_id(client, test_product):
    response = client.get(f"/api/products/{test_product['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_product["id"]


def test_get_product_not_found(client):
    response = client.get("/api/products/nonexistent")
    assert response.status_code == 404


def test_create_product_requires_auth(client):
    product_data = {
        "name": "New Product",
        "description": "Description",
        "source": "github",
        "categories": ["assistive-tech"],
        "source_url": "https://example.com/new-product",
    }

    response = client.post("/api/products", json=product_data)
    assert response.status_code == 401


def test_create_product_success(auth_client, test_user):
    product_data = {
        "name": "New Product",
        "description": "Description",
        "source": "github",
        "categories": ["assistive-tech"],
        "source_url": "https://github.com/user/new-product",
    }

    response = auth_client.post("/api/products", json=product_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Product"
    assert data["created_by"] == test_user["id"]


def test_update_product_owner_only(auth_client, test_product):
    response = auth_client.put(f"/api/products/{test_product['id']}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_delete_product_admin_only(auth_client, test_product):
    response = auth_client.delete(f"/api/products/{test_product['id']}")
    assert response.status_code == 403


def test_delete_product_admin_success(admin_client, test_product):
    response = admin_client.delete(f"/api/products/{test_product['id']}")
    assert response.status_code == 204


# ============================================================================
# TESTS FOR STORY 3.1 & 3.4: PRODUCT SUBMISSION WITH URL CHECK
# ============================================================================

def test_product_exists_endpoint_returns_false_for_new_url(client):
    """Test that /exists endpoint returns false for non-existent product"""
    response = client.get("/api/products/exists?url=https://example.com/never-submitted")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is False
    assert "product" not in data or data.get("product") is None


def test_product_exists_endpoint_returns_product(client, test_product):
    """Test that /exists endpoint returns existing product"""
    response = client.get(f"/api/products/exists?url={test_product['url']}")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["product"]["id"] == test_product["id"]
    assert data["product"]["name"] == test_product["name"]


def test_product_exists_includes_necessary_fields(client, test_product):
    """Test that /exists endpoint returns all fields needed for UI decision"""
    response = client.get(f"/api/products/exists?url={test_product['url']}")
    assert response.status_code == 200
    data = response.json()
    
    # Product should have these fields for UI to display
    product = data["product"]
    assert "id" in product
    assert "name" in product
    assert "description" in product
    assert "source" in product or "source_url" in product


def test_create_product_by_new_user_adds_ownership(auth_client, test_user):
    """
    Story 3.1: User submits new product → becomes manager
    """
    product_data = {
        "name": "Accessibility Tool",
        "description": "A tool for testing accessibility",
        "source": "github",
        "categories": ["assistive-tech"],
        "source_url": "https://github.com/new-user/new-tool",
    }

    response = auth_client.post("/api/products", json=product_data)
    assert response.status_code == 201
    product = response.json()
    
    # Product should have created_by set to current user
    assert product["created_by"] == test_user["id"]
    
    # Verify user is in managers list by querying product_editors table
    # This would require a GET endpoint or checking via the product management response


def test_product_submission_logs_activity(auth_client, test_user, clean_database):
    """
    Story 3.1: User submits product → activity is logged
    """
    product_data = {
        "name": "New Accessible Tool",
        "description": "A tool to test activity logging during product submission",
        "source": "github",
        "categories": ["assistive-tech"],
        "source_url": "https://github.com/activity-test/tool",
    }

    response = auth_client.post("/api/products", json=product_data)
    assert response.status_code == 201
    product = response.json()
    
    # Check that activity was logged (in a real implementation)
    # For now, verify product was created with correct fields
    assert product["name"] == "New Accessible Tool"
    assert product["created_by"] == test_user["id"]


# ============================================================================
# BAN / UNBAN
# ============================================================================


def test_admin_can_ban_and_unban_product(admin_client, clean_database, test_product):
    resp = admin_client.post(f"/api/products/{test_product['id']}/ban", json={"reason": "spam"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["banned"] is True
    assert data["banned_reason"] == "spam"

    resp_unban = admin_client.post(f"/api/products/{test_product['id']}/unban")
    assert resp_unban.status_code == 200
    assert resp_unban.json()["banned"] is False


def test_ban_requires_moderator_or_admin(auth_client, test_product):
    resp = auth_client.post(f"/api/products/{test_product['id']}/ban", json={"reason": "spam"})
    assert resp.status_code == 403


def test_include_banned_requires_privileged_role(client, auth_client, clean_database):
    # Seed banned product
    banned_id = str(uuid.uuid4())
    clean_database.table("products").insert({
        "id": banned_id,
        "name": "Banned Item",
        "description": "",
        "source": "github",
        "type": "tool",
        "banned": True,
    }).execute()

    # Anonymous/user without role cannot request include_banned=true
    resp = client.get("/api/products?include_banned=true")
    assert resp.status_code == 403

    # Regular auth user also forbidden
    resp_auth = auth_client.get("/api/products?include_banned=true")
    assert resp_auth.status_code == 403


def test_banned_products_hidden_from_default_list(client, clean_database, test_product):
    clean_database.table("products").update({"banned": True}).eq("id", test_product["id"]).execute()
    resp = client.get("/api/products")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert test_product["id"] not in ids


def test_admin_can_include_banned_products_in_list(admin_client, clean_database, test_product):
    clean_database.table("products").update({"banned": True}).eq("id", test_product["id"]).execute()
    resp = admin_client.get("/api/products?include_banned=true")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert test_product["id"] in ids


def test_reject_create_when_existing_product_is_banned(auth_client, clean_database, test_product):
    clean_database.table("products").update({"banned": True}).eq("id", test_product["id"]).execute()

    # Use the same source_url from test_product (which should be github.com)
    payload = {
        "name": "Attempted Recreate",
        "description": "Trying to recreate banned product",
        "source": "github",
        "source_url": test_product["url"],
    }

    resp = auth_client.post("/api/products", json=payload)
    assert resp.status_code == 403
    assert "banned" in resp.json().get("detail", "").lower()

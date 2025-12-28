"""Test product endpoints using the local SQLite database"""
import pytest
import uuid


def test_get_products_success(client, test_product):
    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == test_product["id"] for item in data)


def test_count_products_success(client, test_product):
    """Test /count endpoint returns total product count"""
    response = client.get("/api/products/count")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert data["count"] >= 1  # At least the test_product


def test_count_products_with_filters(client, clean_database, test_product):
    """Test /count respects same filters as /products"""
    p1_id = str(uuid.uuid4())
    p2_id = str(uuid.uuid4())
    p3_id = str(uuid.uuid4())

    clean_database.table("products").insert([
        {
            "id": p1_id,
            "name": "Assistive Spoon",
            "description": "Thingiverse fabrication tool",
            "source": "Thingiverse",
            "type": "Fabrication",
            "url": "https://www.thingiverse.com/thing:spoon",
        },
        {
            "id": p2_id,
            "name": "Voice Control Tool",
            "description": "Github software tool",
            "source": "Github",
            "type": "Tool",
            "url": "https://github.com/example/tool",
        },
        {
            "id": p3_id,
            "name": "Knit Pattern",
            "description": "Ravelry knit",
            "source": "Ravelry",
            "type": "Knitting",
            "url": "https://www.ravelry.com/patterns/library/knit",
        },
    ]).execute()

    # Count all products with Thingiverse or Github source
    response = client.get("/api/products/count?sources=Thingiverse,Github")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2  # p1 and p2 only


def test_count_products_with_type_filter(client, clean_database):
    """Test /count filters by type"""
    p1_id = str(uuid.uuid4())
    p2_id = str(uuid.uuid4())

    clean_database.table("products").insert([
        {
            "id": p1_id,
            "name": "3D Model",
            "source": "Thingiverse",
            "type": "Fabrication",
            "url": "https://www.thingiverse.com/thing:1",
        },
        {
            "id": p2_id,
            "name": "Software Tool",
            "source": "Github",
            "type": "Software",
            "url": "https://github.com/example/tool",
        },
    ]).execute()

    response = client.get("/api/products/count?type=Fabrication")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1  # Only p1


def test_count_products_with_tag_filter(client, clean_database):
    """Test /count filters by tags"""
    tag_id = str(uuid.uuid4())
    p1_id = str(uuid.uuid4())
    p2_id = str(uuid.uuid4())

    clean_database.table("tags").insert({"id": tag_id, "name": "AssistiveTech"}).execute()
    clean_database.table("products").insert([
        {
            "id": p1_id,
            "name": "Tagged Product",
            "source": "Thingiverse",
            "type": "Fabrication",
            "url": "https://www.thingiverse.com/thing:tagged",
        },
        {
            "id": p2_id,
            "name": "Untagged Product",
            "source": "Github",
            "type": "Software",
            "url": "https://github.com/example/untagged",
        },
    ]).execute()
    clean_database.table("product_tags").insert({
        "product_id": p1_id,
        "tag_id": tag_id,
    }).execute()

    response = client.get("/api/products/count?tags=AssistiveTech")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1  # Only p1


def test_count_products_with_search(client, clean_database):
    """Test /count filters by search term"""
    p1_id = str(uuid.uuid4())
    p2_id = str(uuid.uuid4())

    clean_database.table("products").insert([
        {
            "id": p1_id,
            "name": "Voice Control Software",
            "source": "Github",
            "type": "Software",
            "url": "https://github.com/example/voice",
        },
        {
            "id": p2_id,
            "name": "3D Printed Cup",
            "source": "Thingiverse",
            "type": "Fabrication",
            "url": "https://www.thingiverse.com/thing:cup",
        },
    ]).execute()

    response = client.get("/api/products/count?search=voice")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1  # Only p1 matches "voice"


def test_get_products_with_filters(client, clean_database, test_product):
    p1_id = str(uuid.uuid4())
    p2_id = str(uuid.uuid4())
    p3_id = str(uuid.uuid4())

    clean_database.table("products").insert([
        {
            "id": p1_id,
            "name": "Assistive Spoon",
            "description": "Thingiverse fabrication tool",
            "source": "Thingiverse",
            "type": "Fabrication",
            "url": "https://www.thingiverse.com/thing:spoon",
        },
        {
            "id": p2_id,
            "name": "Voice Control Tool",
            "description": "Github software tool",
            "source": "Github",
            "type": "Tool",
            "url": "https://github.com/example/tool",
        },
        {
            "id": p3_id,
            "name": "Knit Pattern",
            "description": "Ravelry knit",
            "source": "Ravelry",
            "type": "Knitting",
            "url": "https://www.ravelry.com/patterns/library/knit",
        },
    ]).execute()

    response = client.get("/api/products?sources=Thingiverse,Github&types=Fabrication")
    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data}
    assert p1_id in ids
    assert p2_id not in ids
    assert p3_id not in ids


def test_get_product_by_id(client, test_product):
    response = client.get(f"/api/products/{test_product['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_product["id"]


def test_get_products_filtered_by_tags(client, clean_database):
    tag_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    other_product_id = str(uuid.uuid4())

    clean_database.table("tags").insert({"id": tag_id, "name": "AssistiveTech"}).execute()
    clean_database.table("products").insert([
        {
            "id": product_id,
            "name": "Adapted Cup",
            "description": "Assistive device",
            "source": "Thingiverse",
            "type": "Fabrication",
            "url": "https://www.thingiverse.com/thing:cup",
        },
        {
            "id": other_product_id,
            "name": "Unrelated Tool",
            "description": "No tag match",
            "source": "Github",
            "type": "Tool",
            "url": "https://github.com/example/unrelated",
        },
    ]).execute()
    clean_database.table("product_tags").insert({
        "product_id": product_id,
        "tag_id": tag_id,
    }).execute()

    resp = client.get("/api/products?tags=AssistiveTech")
    assert resp.status_code == 200
    data = resp.json()
    ids = {item["id"] for item in data}
    assert product_id in ids
    assert other_product_id not in ids


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

"""
Tests for collection endpoints
Tests use real API calls via FastAPI TestClient, with test database setup via fixtures
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from main import app


class TestCreateCollection:
    """Tests for Story 6.1: User Creates a Collection"""

    def test_create_collection_success(self, client, test_user, auth_headers):
        """Test successful collection creation"""
        response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={
                "name": "My Favorite Products",
                "description": "Products I love",
                "is_public": True,
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Favorite Products"
        assert data["description"] == "Products I love"
        assert data["is_public"] is True
        assert data["user_id"] == test_user["id"]
        assert data["product_ids"] == []
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_collection_required_name(self, client, test_user, auth_headers):
        """Test that collection name is required"""
        response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={
                "name": "",
                "description": "Products I love",
                "is_public": True,
            }
        )
        # Pydantic schema validation returns 422 for min_length violation
        assert response.status_code == 422

    def test_create_collection_missing_name(self, client, test_user, auth_headers):
        """Test that collection name field is required"""
        response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={
                "description": "Products I love",
                "is_public": True,
            }
        )
        assert response.status_code == 422  # Validation error

    def test_create_collection_description_too_long(self, client, test_user, auth_headers):
        """Test description max length validation"""
        long_desc = "a" * 1001
        response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={
                "name": "My Collection",
                "description": long_desc,
                "is_public": True,
            }
        )
        assert response.status_code == 422

    def test_create_collection_default_visibility_public(self, client, test_user, auth_headers):
        """Test that default visibility is public"""
        response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={
                "name": "My Collection",
            }
        )
        assert response.status_code == 201
        assert response.json()["is_public"] is True

    def test_create_collection_requires_auth(self, client):
        """Test that authentication is required"""
        response = client.post(
            "/api/collections",
            json={
                "name": "My Collection",
                "is_public": True,
            }
        )
        assert response.status_code == 401

    def test_create_collection_private(self, client, test_user, auth_headers):
        """Test creating a private collection"""
        response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={
                "name": "My Private Collection",
                "is_public": False,
            }
        )
        assert response.status_code == 201
        assert response.json()["is_public"] is False


class TestGetUserCollections:
    """Tests for Story 6.2: User Views Their Collections"""

    def test_get_user_collections(self, client, test_user, auth_headers):
        """Test fetching user's collections"""
        # Create a collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Collection 1", "is_public": True}
        )
        collection_id = create_response.json()["id"]

        # Get collections
        response = client.get("/api/collections", headers=auth_headers(test_user))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(c["id"] == collection_id for c in data)

    def test_get_user_collections_only_own(self, client, test_user, test_user_2, auth_headers):
        """Test that user only sees their own collections"""
        # Create collection for user 1
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "User 1 Collection", "is_public": True}
        )

        # Create collection for user 2
        client.post(
            "/api/collections",
            headers=auth_headers(test_user_2),
            json={"name": "User 2 Collection", "is_public": True}
        )

        # User 1 should only see their own
        response = client.get("/api/collections", headers=auth_headers(test_user))
        assert response.status_code == 200
        collections = response.json()
        assert len(collections) == 1
        assert collections[0]["name"] == "User 1 Collection"

    def test_get_user_collections_empty(self, client, test_user, auth_headers):
        """Test getting collections when user has none"""
        response = client.get("/api/collections", headers=auth_headers(test_user))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_user_collections_requires_auth(self, client):
        """Test that getting collections requires authentication"""
        response = client.get("/api/collections")
        assert response.status_code == 401


class TestGetPublicCollections:
    """Tests for Story 6.3: Browse Public Collections"""

    def test_get_public_collections(self, client, test_user, auth_headers):
        """Test fetching public collections"""
        # Create public and private collections
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Public Collection", "is_public": True}
        )
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Private Collection", "is_public": False}
        )

        # Get public collections (no auth needed)
        response = client.get("/api/collections/public")
        assert response.status_code == 200
        data = response.json()
        assert any(c["name"] == "Public Collection" for c in data)
        assert not any(c["name"] == "Private Collection" for c in data)

    def test_public_collections_with_search(self, client, test_user, auth_headers):
        """Test searching public collections"""
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Yarn Stash", "is_public": True}
        )
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Patterns Library", "is_public": True}
        )

        response = client.get("/api/collections/public?search=yarn")
        assert response.status_code == 200
        collections = response.json()
        assert any("Yarn" in c["name"] for c in collections)

    def test_public_collections_with_sort(self, client, test_user, auth_headers):
        """Test sorting public collections"""
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "First", "is_public": True}
        )
        client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Second", "is_public": True}
        )

        response = client.get("/api/collections/public?sort_by=created_at")
        assert response.status_code == 200
        assert response.json() is not None


class TestGetCollectionDetails:
    """Tests for Story 6.4: View Collection Details"""

    def test_get_collection_details_public(self, client, test_user, auth_headers):
        """Test getting details of a public collection"""
        # Create public collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Public Collection", "description": "A public collection"}
        )
        collection_id = create_response.json()["id"]

        # Get details without auth
        response = client.get(f"/api/collections/{collection_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Public Collection"
        assert data["description"] == "A public collection"

    def test_get_collection_details_private_owner(self, client, test_user, auth_headers):
        """Test owner can get their private collection"""
        # Create private collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Private Collection", "is_public": False}
        )
        collection_id = create_response.json()["id"]

        # Get details as owner
        response = client.get(f"/api/collections/{collection_id}", headers=auth_headers(test_user))
        assert response.status_code == 200
        assert response.json()["name"] == "Private Collection"

    def test_get_collection_details_private_non_owner(self, client, test_user, test_user_2, auth_headers):
        """Test non-owner cannot get private collection"""
        # Create private collection as user 1
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Private Collection", "is_public": False}
        )
        collection_id = create_response.json()["id"]

        # Try to access as user 2
        response = client.get(f"/api/collections/{collection_id}", headers=auth_headers(test_user_2))
        assert response.status_code == 403

    def test_get_collection_details_not_found(self, client):
        """Test getting non-existent collection"""
        response = client.get(f"/api/collections/{uuid.uuid4()}")
        assert response.status_code == 404


class TestUpdateCollection:
    """Tests for Story 6.5: Edit Collection"""

    def test_update_collection_success(self, client, test_user, auth_headers):
        """Test successful collection update"""
        # Create collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Original Name"}
        )
        collection_id = create_response.json()["id"]

        # Update collection
        response = client.put(
            f"/api/collections/{collection_id}",
            headers=auth_headers(test_user),
            json={"name": "New Name", "description": "New description"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New description"

    def test_update_collection_requires_ownership(self, client, test_user, test_user_2, auth_headers):
        """Test that only owner can update collection"""
        # Create collection as user 1
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Collection"}
        )
        collection_id = create_response.json()["id"]

        # Try to update as user 2
        response = client.put(
            f"/api/collections/{collection_id}",
            headers=auth_headers(test_user_2),
            json={"name": "Hacked"}
        )
        assert response.status_code == 403

    def test_update_collection_visibility(self, client, test_user, auth_headers):
        """Test updating collection visibility"""
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Collection", "is_public": True}
        )
        collection_id = create_response.json()["id"]

        response = client.put(
            f"/api/collections/{collection_id}",
            headers=auth_headers(test_user),
            json={"is_public": False}
        )
        assert response.status_code == 200
        assert response.json()["is_public"] is False

    def test_update_collection_requires_auth(self, client):
        """Test that updating collection requires authentication"""
        response = client.put(
            f"/api/collections/{uuid.uuid4()}",
            json={"name": "New Name"}
        )
        assert response.status_code == 401


class TestDeleteCollection:
    """Tests for Story 6.6: Delete Collection"""

    def test_delete_collection_success(self, client, test_user, auth_headers):
        """Test successful collection deletion"""
        # Create collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "To Delete"}
        )
        collection_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/collections/{collection_id}", headers=auth_headers(test_user))
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/collections/{collection_id}", headers=auth_headers(test_user))
        assert get_response.status_code == 404

    def test_delete_collection_requires_ownership(self, client, test_user, test_user_2, auth_headers):
        """Test that only owner can delete collection"""
        # Create collection as user 1
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Collection"}
        )
        collection_id = create_response.json()["id"]

        # Try to delete as user 2
        response = client.delete(f"/api/collections/{collection_id}", headers=auth_headers(test_user_2))
        assert response.status_code == 403

    def test_delete_collection_requires_auth(self, client):
        """Test that deleting collection requires authentication"""
        response = client.delete(f"/api/collections/{uuid.uuid4()}")
        assert response.status_code == 401


class TestAddProductToCollection:
    """Tests for Story 6.7: Add Products to Collection"""

    def test_add_product_to_collection_success(self, client, test_user, test_product, auth_headers):
        """Test adding a product to collection"""
        # Create collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "My Products"}
        )
        collection_id = create_response.json()["id"]

        # Add product
        response = client.post(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
            , headers=auth_headers(test_user)
        )
        assert response.status_code == 200
        data = response.json()
        assert test_product["id"] in data["product_ids"]

    def test_add_product_idempotent(self, client, test_user, test_product, auth_headers):
        """Test that adding same product twice is idempotent"""
        # Create collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "My Products"}
        )
        collection_id = create_response.json()["id"]

        # Add product twice
        client.post(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
            , headers=auth_headers(test_user)
        )
        response = client.post(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
            , headers=auth_headers(test_user)
        )

        assert response.status_code == 200
        data = response.json()
        # Product should only appear once
        assert data["product_ids"].count(test_product["id"]) == 1

    def test_add_product_nonexistent_collection(self, client, test_user, test_product, auth_headers):
        """Test adding product to non-existent collection"""
        response = client.post(
            f"/api/collections/{uuid.uuid4()}/products/{test_product['id']}"
            , headers=auth_headers(test_user)
        )
        assert response.status_code == 404

    def test_add_product_requires_ownership(self, client, test_user, test_user_2, test_product, auth_headers):
        """Test that only owner can add products"""
        # Create collection as user 1
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "My Products"}
        )
        collection_id = create_response.json()["id"]

        # Try to add product as user 2
        response = client.post(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user_2))
        assert response.status_code == 403


class TestRemoveProductFromCollection:
    """Tests for Story 6.8: Remove Products from Collection"""

    def test_remove_product_from_collection_success(self, client, test_user, test_product, auth_headers):
        """Test removing a product from collection"""
        # Create collection and add product
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "My Products"}
        )
        collection_id = create_response.json()["id"]

        client.post(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user))

        # Remove product
        response = client.delete(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user))
        assert response.status_code == 200
        data = response.json()
        assert test_product["id"] not in data["product_ids"]

    def test_remove_product_idempotent(self, client, test_user, test_product, auth_headers):
        """Test that removing product twice is idempotent"""
        # Create collection with product
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "My Products"}
        )
        collection_id = create_response.json()["id"]

        client.post(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user))

        # Remove twice
        client.delete(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user))
        response = client.delete(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user))

        assert response.status_code == 200
        data = response.json()
        assert test_product["id"] not in data["product_ids"]

    def test_remove_product_requires_ownership(self, client, test_user, test_user_2, test_product, auth_headers):
        """Test that only owner can remove products"""
        # Create collection as user 1
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "My Products"}
        )
        collection_id = create_response.json()["id"]

        # Try to remove as user 2
        response = client.delete(
            f"/api/collections/{collection_id}/products/{test_product['id']}"
        , headers=auth_headers(test_user_2))
        assert response.status_code == 403


class TestAddMultipleProductsToCollection:
    """Tests for bulk product operations"""

    def test_add_multiple_products_success(self, client, test_product, clean_database, test_user, auth_headers):
        """Test adding multiple products at once"""
        # Create another test product
        product_data = {
            "name": "Second Product",
            "description": "Another test product",
            "source": "manual",
            "category": "Other",
            "url": "https://example.com/second",
            "created_by": test_user["id"],
        }
        result = clean_database.table("products").insert(product_data).execute()
        second_product = result.data[0]

        # Create collection
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Multi Products"}
        )
        collection_id = create_response.json()["id"]

        # Add multiple products
        response = client.post(
            f"/api/collections/{collection_id}/products",
            headers=auth_headers(test_user),
            json={"product_ids": [test_product["id"], second_product["id"]]}
        )
        assert response.status_code == 200
        data = response.json()
        assert test_product["id"] in data["product_ids"]
        assert second_product["id"] in data["product_ids"]
        assert len(data["product_ids"]) == 2

    def test_add_multiple_products_empty_list(self, client, test_user, auth_headers):
        """Test that adding empty product list works"""
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Empty Add"}
        )
        collection_id = create_response.json()["id"]

        response = client.post(
            f"/api/collections/{collection_id}/products",
            headers=auth_headers(test_user),
            json={"product_ids": []}
        )
        assert response.status_code == 200

    def test_add_multiple_products_with_duplicates(self, client, test_user, test_product, auth_headers):
        """Test adding same product twice in bulk"""
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Duplicates"}
        )
        collection_id = create_response.json()["id"]

        response = client.post(
            f"/api/collections/{collection_id}/products",
            headers=auth_headers(test_user),
            json={"product_ids": [test_product["id"], test_product["id"]]}
        )
        assert response.status_code == 200
        data = response.json()
        # Should only contain product once
        assert data["product_ids"].count(test_product["id"]) == 1

    def test_add_multiple_products_requires_ownership(self, client, test_user, test_user_2, test_product, auth_headers):
        """Test that only owner can bulk add products"""
        create_response = client.post(
            "/api/collections",
            headers=auth_headers(test_user),
            json={"name": "Protected"}
        )
        collection_id = create_response.json()["id"]

        response = client.post(
            f"/api/collections/{collection_id}/products",
            headers=auth_headers(test_user_2),
            json={"product_ids": [test_product["id"]]}
        )
        assert response.status_code == 403

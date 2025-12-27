"""Collection management endpoints.

Supports user-curated product collections with public/private visibility.
All mutations require authentication and enforce ownership checks.
Security: Users can only modify their own collections unless admin.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, UTC
from models.collections import CollectionCreate, CollectionUpdate, CollectionResponse, ProductIdsRequest
from services.database import get_db
from services.auth import get_current_user, get_current_user_optional
import uuid

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    collection_data: CollectionCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Create a new collection for the authenticated user.
    
    Generates human-readable ID from collection name (e.g., "my-collection").
    Security: Requires authentication; collection automatically associated with creator.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    user_name = current_user.get("username", "Unknown")
    
    # Validate input
    if not collection_data.name or not collection_data.name.strip():
        raise HTTPException(status_code=400, detail="Collection name is required")
    
    if collection_data.description and len(collection_data.description) > 1000:
        raise HTTPException(status_code=400, detail="Description must be 1000 characters or less")
    
    # Generate UUID primary key (schema expects UUID)
    collection = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_name": user_name,
        "name": collection_data.name,
        "description": collection_data.description,
        "product_ids": [],
        "is_public": collection_data.is_public,
    }
    
    # Insert into database
    response = db.table("collections").insert(collection).execute()
    
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create collection")
    
    return response.data[0]


@router.get("", response_model=List[CollectionResponse])
async def get_user_collections(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Get all collections for the authenticated user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    
    # Fetch collections from database
    response = db.table("collections").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    
    return response.data or []


@router.get("/public", response_model=List[CollectionResponse])
async def get_public_collections(
    sort_by: str = Query("created_at", pattern=r"^(created_at|product_count|updated_at)$"),
    search: Optional[str] = None,
    db = Depends(get_db),
):
    """Get all public collections, optionally sorted and filtered.
    
    Privacy: Only returns collections with is_public=true.
    Supports sorting by created_at (default), product_count, or updated_at.
    Optional search filters by collection name (case-insensitive).
    """
    # Fetch public collections
    response = db.table("collections").select("*").eq("is_public", True).execute()
    
    collections = response.data or []
    
    # Filter by search if provided
    if search:
        search_lower = search.lower()
        collections = [c for c in collections if search_lower in c.get("name", "").lower()]
    
    # Sort
    if sort_by == "product_count":
        collections.sort(key=lambda c: len(c.get("product_ids", []) or []), reverse=True)
    elif sort_by == "updated_at":
        collections.sort(key=lambda c: c.get("updated_at", c.get("created_at")), reverse=True)
    else:  # created_at
        collections.sort(key=lambda c: c.get("created_at"), reverse=True)
    
    return collections


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db),
):
    """Get collection details - public collections viewable by all, private only by owner"""
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = response.data[0]
    
    # Check access
    if not collection.get("is_public"):
        if not current_user or current_user.get("id") != collection.get("user_id"):
            raise HTTPException(status_code=403, detail="Access denied")
    
    return collection


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    collection_data: CollectionUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Update collection - only owner can edit"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    
    # Get collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = response.data[0]
    
    # Check ownership
    if collection.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can edit this collection")
    
    # Validate input
    if collection_data.name is not None:
        if not collection_data.name.strip():
            raise HTTPException(status_code=400, detail="Collection name cannot be empty")
    
    if collection_data.description is not None and len(collection_data.description) > 1000:
        raise HTTPException(status_code=400, detail="Description must be 1000 characters or less")
    
    # Build update data
    update_data = {}
    if collection_data.name is not None:
        update_data["name"] = collection_data.name
    if collection_data.description is not None:
        update_data["description"] = collection_data.description
    if collection_data.is_public is not None:
        update_data["is_public"] = collection_data.is_public
    
    update_data["updated_at"] = datetime.now(UTC)
    
    # Update in database
    response = db.table("collections").update(update_data).eq("id", collection_id).execute()
    
    return response.data[0]


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Delete collection - only owner can delete"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    
    # Get collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = response.data[0]
    
    # Check ownership
    if collection.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this collection")
    
    # Delete from database
    db.table("collections").delete().eq("id", collection_id).execute()
    
    return None


@router.post("/{collection_id}/products/{product_id}", response_model=CollectionResponse)
async def add_product_to_collection(
    collection_id: str,
    product_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Add a product to a collection"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    
    # Get collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = response.data[0]
    
    # Check ownership
    if collection.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can modify this collection")
    
    # Check product exists
    products = db.table("products").select("id").eq("id", product_id).execute()
    if not products.data:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Add product if not already in collection
    product_ids = collection.get("product_ids", []) or []
    if product_id not in product_ids:
        product_ids.append(product_id)
        
        # Update collection
        db.table("collections").update({
            "product_ids": product_ids,
            "updated_at": datetime.now(UTC)
        }).eq("id", collection_id).execute()
    
    # Return updated collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    return response.data[0]


@router.delete("/{collection_id}/products/{product_id}", response_model=CollectionResponse)
async def remove_product_from_collection(
    collection_id: str,
    product_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Remove a product from a collection"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    
    # Get collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = response.data[0]
    
    # Check ownership
    if collection.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can modify this collection")
    
    # Remove product
    product_ids = collection.get("product_ids", []) or []
    if product_id in product_ids:
        product_ids.remove(product_id)
        
        # Update collection
        db.table("collections").update({
            "product_ids": product_ids,
            "updated_at": datetime.now(UTC)
        }).eq("id", collection_id).execute()
    
    # Return updated collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    return response.data[0]


@router.post("/{collection_id}/products", response_model=CollectionResponse)
async def add_multiple_products_to_collection(
    collection_id: str,
    request: ProductIdsRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Add multiple products to a collection at once"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_id = current_user.get("id")
    product_ids = request.product_ids
    
    # Get collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection = response.data[0]
    
    # Check ownership
    if collection.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Only the owner can modify this collection")
    
    # Idempotent behavior: Empty list is allowed (returns collection unchanged)
    if not product_ids:
        response = db.table("collections").select("*").eq("id", collection_id).execute()
        return response.data[0]
    
    # Verify all products exist
    for prod_id in product_ids:
        products = db.table("products").select("id").eq("id", prod_id).execute()
        if not products.data:
            raise HTTPException(status_code=404, detail=f"Product {prod_id} not found")
    
    # Add products, avoiding duplicates
    current_product_ids = collection.get("product_ids", []) or []
    for prod_id in product_ids:
        if prod_id not in current_product_ids:
            current_product_ids.append(prod_id)
    
    # Update collection
    db.table("collections").update({
        "product_ids": current_product_ids,
        "updated_at": datetime.now(UTC)
    }).eq("id", collection_id).execute()
    
    # Return updated collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    return response.data[0]

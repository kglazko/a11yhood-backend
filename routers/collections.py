"""Collection management endpoints.

Supports user-curated product collections with public/private visibility.
All mutations require authentication and enforce ownership checks.
Security: Users can only modify their own collections unless admin.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime, UTC
from models.collections import CollectionCreate, CollectionUpdate, CollectionResponse, ProductIdsRequest, CollectionFromSearchCreate
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


@router.post("/from-search", response_model=CollectionResponse, status_code=201)
async def create_collection_from_search(
    collection_data: CollectionFromSearchCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Create a new collection and populate it with search results.
    
    Takes the same search parameters as GET /api/products and creates a collection
    with all matching products. The collection is automatically associated with the
    authenticated user.
    
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
    
    # Build search query using the same logic as GET /api/products
    query = db.table("products").select("id")
    
    # Normalize source filters
    source_values = set()
    if collection_data.source:
        source_values.update(collection_data.source)
    if collection_data.sources:
        source_values.update(collection_data.sources)
    
    # Canonicalize sources
    if source_values:
        try:
            rows = db.table("supported_sources").select("name").execute()
            name_map = {
                str(r.get("name")).strip().lower(): str(r.get("name")).strip() 
                for r in (rows.data or []) if r.get("name")
            }
            canonical_sources = []
            for v in source_values:
                key = str(v).strip().lower()
                canonical_sources.append(name_map.get(key, v))
            # Deduplicate while preserving order
            seen = set()
            source_values = []
            for c in canonical_sources:
                if c not in seen:
                    seen.add(c)
                    source_values.append(c)
        except Exception:
            source_values = list(source_values)
        
        query = query.in_("source", source_values)
    
    # Normalize type filters
    type_values = set()
    if collection_data.type:
        type_values.update(collection_data.type)
    if collection_data.types:
        type_values.update(collection_data.types)
    
    if type_values:
        query = query.in_("type", list(type_values))
    
    # Handle tags
    if collection_data.tags:
        tag_mode = collection_data.tags_mode.lower()
        product_ids_with_tags = _get_product_ids_for_tags(db, collection_data.tags, tag_mode)
        if not product_ids_with_tags:
            # No products match the tag filter, create empty collection
            product_ids = []
        else:
            # Apply text search and other filters to tag-filtered products
            query = query.in_("id", list(product_ids_with_tags))
            
            if collection_data.search:
                query = query.ilike("name", f"%{collection_data.search}%")
            
            if collection_data.created_by:
                query = query.eq("created_by", collection_data.created_by)
            
            if collection_data.min_rating is not None:
                # For min_rating, we'll filter in Python after fetching all matches
                # since we need rating data
                query = query.eq("banned", False)
                query = query.order("created_at", desc=True)
                response = query.execute()
                products = response.data or []
                
                if products and collection_data.min_rating is not None:
                    # Build rating map
                    product_ids = [p.get("id") for p in products if p.get("id")]
                    if product_ids:
                        ratings_map = _build_display_rating_map(db, products)
                        product_ids = [
                            p.get("id") for p in products
                            if p.get("id") and _rating_meets_threshold(p, ratings_map, collection_data.min_rating)
                        ]
                    else:
                        product_ids = []
                else:
                    product_ids = [p.get("id") for p in products if p.get("id")]
            else:
                query = query.eq("banned", False)
                query = query.order("created_at", desc=True)
                response = query.execute()
                products = response.data or []
                product_ids = [p.get("id") for p in products if p.get("id")]
    else:
        # No tag filter, apply other filters directly
        if collection_data.search:
            query = query.ilike("name", f"%{collection_data.search}%")
        
        if collection_data.created_by:
            query = query.eq("created_by", collection_data.created_by)
        
        query = query.eq("banned", False)
        query = query.order("created_at", desc=True)
        response = query.execute()
        products = response.data or []
        product_ids = [p.get("id") for p in products if p.get("id")]
        
        # Apply min_rating filter if specified
        if collection_data.min_rating is not None and product_ids:
            ratings_map = _build_display_rating_map(db, products)
            product_ids = [
                p.get("id") for p in products
                if p.get("id") and _rating_meets_threshold(p, ratings_map, collection_data.min_rating)
            ]
    
    # Create the collection with the search results
    collection = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_name": user_name,
        "name": collection_data.name,
        "description": collection_data.description,
        "product_ids": product_ids,
        "is_public": collection_data.is_public,
    }
    
    # Insert into database
    response = db.table("collections").insert(collection).execute()
    
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create collection")
    
    return response.data[0]


def _get_product_ids_for_tags(db, tag_names: list[str], mode: str = "or") -> set[str]:
    """Return product IDs that match provided tag names using OR/AND semantics."""
    if not tag_names:
        return set()
    tag_rows = db.table("tags").select("id,name").in_("name", tag_names).execute()
    tag_map = {row["name"]: row["id"] for row in (tag_rows.data or []) if row.get("id") and row.get("name")}
    tag_ids = [tag_map[name] for name in tag_names if name in tag_map]
    if not tag_ids:
        return set()

    pt_rows = db.table("product_tags").select("product_id, tag_id").in_("tag_id", tag_ids).execute()
    if not pt_rows.data:
        return set()

    if mode == "and":
        required = set(tag_ids)
        product_tag_map: dict[str, set[str]] = {}
        for row in pt_rows.data:
            pid = row.get("product_id")
            tid = row.get("tag_id")
            if pid and tid:
                product_tag_map.setdefault(pid, set()).add(tid)
        return {pid for pid, tids in product_tag_map.items() if required.issubset(tids)}

    return {row["product_id"] for row in pt_rows.data if row.get("product_id")}


def _safe_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _compute_display_rating(user_average: Optional[float], source_rating: Optional[float]) -> Optional[float]:
    if user_average is not None and source_rating is not None:
        return (user_average + source_rating) / 2
    if user_average is not None:
        return user_average
    if source_rating is not None:
        return source_rating
    return None


def _build_display_rating_map(db, products: list[dict]) -> dict[str, dict]:
    """Compute display ratings and counts keyed by product ID."""
    product_ids = [p.get("id") for p in products if p.get("id")]
    if not product_ids:
        return {}

    # Fetch ratings for all products
    ratings_rows: list[dict] = []
    chunk_size = 500
    for i in range(0, len(product_ids), chunk_size):
        chunk = product_ids[i:i + chunk_size]
        resp = db.table("ratings").select("product_id,rating").in_("product_id", chunk).execute()
        ratings_rows.extend(resp.data or [])

    aggregates: dict[str, dict[str, float | int]] = {}
    for row in ratings_rows:
        pid = row.get("product_id")
        rating_raw = row.get("rating")
        rating_val = _safe_float(rating_raw)
        if not pid or rating_val is None:
            continue
        agg = aggregates.setdefault(pid, {"sum": 0.0, "count": 0})
        agg["sum"] += rating_val
        agg["count"] += 1

    ratings_map: dict[str, dict] = {}
    for product in products:
        pid = product.get("id")
        if not pid:
            continue
        agg = aggregates.get(pid, {"sum": 0.0, "count": 0})
        user_avg = (agg["sum"] / agg["count"]) if agg["count"] else None
        source_rating_val = _safe_float(product.get("source_rating"))
        display_rating = _compute_display_rating(user_avg, source_rating_val)
        ratings_map[pid] = {
            "average_rating": user_avg,
            "rating_count": agg.get("count", 0),
            "display_rating": display_rating,
        }
    return ratings_map


def _rating_meets_threshold(product: dict, ratings_map: dict[str, dict], min_rating: float) -> bool:
    rating_info = ratings_map.get(product.get("id"), {})
    display_rating = rating_info.get("display_rating")
    if display_rating is None:
        return False
    return display_rating >= min_rating



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
    
    update_data["updated_at"] = datetime.now(UTC).isoformat()
    
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
            "updated_at": datetime.now(UTC).isoformat()
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
            "updated_at": datetime.now(UTC).isoformat()
        }).eq("id", collection_id).execute()
    
    # Return updated collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    return response.data[0]


@router.delete("/{collection_id}/products", response_model=CollectionResponse)
async def remove_all_products_from_collection(
    collection_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Remove all products from a collection"""
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
    
    # Clear all products
    db.table("collections").update({
        "product_ids": [],
        "updated_at": datetime.now(UTC).isoformat()
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
        "updated_at": datetime.now(UTC).isoformat()
    }).eq("id", collection_id).execute()
    
    # Return updated collection
    response = db.table("collections").select("*").eq("id", collection_id).execute()
    return response.data[0]

"""Product management endpoints.

Handles CRUD operations for products with ownership tracking via product_editors table.
Supports URL-based upsert for scrapers and tag management via relationship tables.
Security: Mutations require authentication; updates/deletes enforce ownership or admin role.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Iterable
from datetime import datetime, UTC

from models.products import ProductCreate, ProductUpdate, ProductResponse
from services.database import get_db
from services.auth import get_current_user, get_current_user_optional
from services.id_generator import generate_id_with_uniqueness_check
from services.sources import extract_domain, find_source_for_domain

router = APIRouter(prefix="/api/products", tags=["products"])


def _normalize_list(values: Optional[Iterable[str]]) -> list[str]:
    """Flatten query params supporting comma-separated and repeated values."""
    normalized: list[str] = []
    for v in values or []:
        if v is None:
            continue
        if not isinstance(v, str):
            v = str(v)
        for part in v.split(","):
            item = part.strip()
            if item:
                normalized.append(item)
    return normalized


@router.get("/sources")
async def get_product_sources(
    db = Depends(get_db),
):
    """Get all unique source values from products table.
    
    Returns a sorted list of distinct sources for filter UI.
    Uses supported_sources as the canonical list so options are stable
    regardless of current search filters.
    """
    try:
        # Prefer canonical supported_sources table so UI always has full list.
        response = db.table("supported_sources").select("name").execute()
        sources = {
            row["name"].strip()
            for row in (response.data or [])
            if row.get("name") and row.get("name").strip()
        }
        # Fallback to distinct product sources if the table is empty/missing.
        if not sources:
            product_sources = db.table("products").select("source").execute()
            sources = {
                row["source"].strip()
                for row in (product_sources.data or [])
                if row.get("source") and row.get("source").strip()
            }
        return {"sources": sorted(sources)}
    except Exception:
        return {"sources": []}


def get_product_ids_for_tags(db, tag_names: list[str], mode: str = "or") -> set[str]:
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


def build_display_rating_map(db, products: list[dict]) -> dict[str, dict]:
    """Compute display ratings and counts keyed by product ID."""
    product_ids = [p.get("id") for p in products if p.get("id")]
    if not product_ids:
        return {}

    # Chunk rating lookups to avoid oversize PostgREST queries when many products are present.
    ratings_rows: list[dict] = []
    chunk_size = 200
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


def rating_meets_threshold(product: dict, ratings_map: dict[str, dict], min_rating: float) -> bool:
    rating_info = ratings_map.get(product.get("id"), {})
    display_rating = rating_info.get("display_rating")
    if display_rating is None:
        return False
    return display_rating >= min_rating


def attach_rating_fields(db, product: dict, ratings_map: Optional[dict[str, dict]] = None) -> dict:
    """Attach average, count, and display rating to a single product record."""
    effective_map = ratings_map if ratings_map is not None else build_display_rating_map(db, [product])
    rating_info = effective_map.get(product.get("id"), {}) if effective_map else {}
    product["average_rating"] = rating_info.get("average_rating")
    product["rating_count"] = rating_info.get("rating_count", product.get("rating_count") or 0)
    product["display_rating"] = rating_info.get("display_rating")
    return product


@router.get("/types")
async def get_product_types(
    db = Depends(get_db),
):
    """Get all unique type values from products table.
    
    Returns a sorted list of distinct types for filter UI.
    Uses valid_categories as the canonical list so options stay stable
    regardless of current search filters.
    """
    try:
        # Prefer canonical valid_categories table.
        response = db.table("valid_categories").select("category").execute()
        types = {
            row["category"].strip()
            for row in (response.data or [])
            if row.get("category") and row.get("category").strip()
        }
        # Fallback to distinct product types if table is empty/missing.
        if not types:
            product_types = db.table("products").select("type").execute()
            types = {row["type"] for row in (product_types.data or []) if row.get("type")}
        return {"types": sorted(types)}
    except Exception as e:
        return {"types": []}


@router.get("/tags")
async def get_popular_tags(
    limit: int = Query(10, le=50),
    db = Depends(get_db),
):
    """Get most popular tags from products.
    
    Returns tags ordered by frequency, limited to specified count.
    Uses product_tags relationship table to count tag usage.
    """
    try:
        # Get all product_tags relationships
        response = db.table("product_tags").select("tag").execute()
        tag_list = [row["tag"] for row in (response.data or []) if row.get("tag")]
        
        # Count tag frequencies
        from collections import Counter
        tag_counts = Counter(tag_list)
        
        # Get top N most common tags
        popular_tags = [tag for tag, count in tag_counts.most_common(limit)]
        return {"tags": popular_tags}
    except Exception as e:
        return {"tags": []}


@router.get("", response_model=list[ProductResponse])
async def get_products(
    source: Optional[list[str]] = Query(None, alias="source", description="Comma-separated or repeated source values"),
    sources: Optional[list[str]] = Query(None, description="Comma-separated or repeated source values"),
    type: Optional[list[str]] = Query(None, alias="type", description="Comma-separated or repeated type values"),
    types: Optional[list[str]] = Query(None, description="Comma-separated or repeated type values"),
    tags: Optional[list[str]] = Query(None, alias="tags", description="Filter products that have any of these tag names"),
    tags_mode: str = Query("or", pattern="^(?i)(or|and)$", description="Tag filter mode: or (default) or and"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum display rating (user or source)"),
    search: Optional[str] = None,
    created_by: Optional[str] = None,
    include_banned: bool = Query(False, description="Include banned products (admin/mod only)"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db),
):
    """Get all products with optional filters.
    
    Loads ownership and tag data via relationship tables to avoid JSON array storage.
    Returns denormalized response with editor_ids and tags attached to each product.
    Query supports filtering by source platform, type, text search, and creator.
    """
    tag_mode = (tags_mode or "or").lower()
    if tag_mode not in {"or", "and"}:
        raise HTTPException(status_code=400, detail="tags_mode must be 'or' or 'and'")

    query = db.table("products").select("*")

    source_values = set(_normalize_list(source) + _normalize_list(sources))
    type_values = set(_normalize_list(type) + _normalize_list(types))
    tag_values = _normalize_list(tags)

    if source_values:
        query = query.in_("source", list(source_values))
    
    if type_values:
        query = query.in_("type", list(type_values))

    if tag_values:
        product_ids_with_tags = get_product_ids_for_tags(db, tag_values, tag_mode)
        if not product_ids_with_tags:
            return []
        query = query.in_("id", list(product_ids_with_tags))
    
    if search:
        query = query.ilike("name", f"%{search}%")
    
    if created_by:
        query = query.eq("created_by", created_by)
    
    if include_banned:
        if not current_user or current_user.get("role") not in {"admin", "moderator"}:
            raise HTTPException(status_code=403, detail="Moderator or admin role required to view banned products")

    apply_range = min_rating is None
    if apply_range:
        query = query.range(offset, offset + limit - 1)

    query = query.order("created_at", desc=True)
    
    response = query.execute()

    # Collect product IDs
    products = response.data or []

    if not include_banned:
        products = [p for p in products if not p.get("banned")]

    ratings_map = build_display_rating_map(db, products)
    if min_rating is not None:
        products = [p for p in products if rating_meets_threshold(p, ratings_map, min_rating)]
        products = products[offset:offset + limit]

    product_ids = [p["id"] for p in products]

    # Load owners for each product
    owners_by_product: dict[str, list[str]] = {}
    if product_ids:
        owners_rows = db.table("product_editors").select("product_id, user_id").in_("product_id", product_ids).execute()
        for row in owners_rows.data or []:
            pid = row.get("product_id")
            uid = row.get("user_id")
            if pid and uid:
                owners_by_product.setdefault(pid, []).append(uid)

    # Load tags via relationship tables
    tags_by_product: dict[str, list[str]] = {}
    if product_ids:
        pt_rows = get_product_tag_rows(db, product_ids)
        tag_ids = list({row["tag_id"] for row in pt_rows}) if pt_rows else []
        tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
        for row in pt_rows:
            pid = row["product_id"]
            tname = tags_map.get(row["tag_id"]) if row["tag_id"] in tags_map else None
            if tname:
                tags_by_product.setdefault(pid, []).append(tname)

    # Normalize fields and attach tags
    normalized = []
    for item in products:
        # Add top-level stars derived from source_rating_count
        item["stars"] = item.get("source_rating_count") or 0
        rating_info = ratings_map.get(item["id"], {})
        item["average_rating"] = rating_info.get("average_rating")
        item["rating_count"] = rating_info.get("rating_count", item.get("rating_count") or 0)
        item["display_rating"] = rating_info.get("display_rating")
        # Normalize fields for API clients
        if "image" in item:
            item["image_url"] = item.get("image")
        if "url" in item:
            item["source_url"] = item.get("url")
        item["tags"] = tags_by_product.get(item["id"], [])
        item["editor_ids"] = owners_by_product.get(item["id"], [])
        normalized.append(item)

    return normalized


@router.get("/count")
async def count_products(
    source: Optional[list[str]] = Query(None, alias="source", description="Comma-separated or repeated source values"),
    sources: Optional[list[str]] = Query(None, description="Comma-separated or repeated source values"),
    type: Optional[list[str]] = Query(None, alias="type", description="Comma-separated or repeated type values"),
    types: Optional[list[str]] = Query(None, description="Comma-separated or repeated type values"),
    tags: Optional[list[str]] = Query(None, alias="tags", description="Filter products that have any of these tag names"),
    tags_mode: str = Query("or", pattern="^(?i)(or|and)$", description="Tag filter mode: or (default) or and"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum display rating (user or source)"),
    search: Optional[str] = None,
    created_by: Optional[str] = None,
    include_banned: bool = Query(False, description="Include banned products (admin/mod only)"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    db = Depends(get_db),
):
    """Get total count of products matching filters (for pagination UI).
    
    Returns {count: int} to help frontend paginate through all matching products.
    Applies same filters as /api/products but returns only the count.
    """
    tag_mode = (tags_mode or "or").lower()
    if tag_mode not in {"or", "and"}:
        raise HTTPException(status_code=400, detail="tags_mode must be 'or' or 'and'")

    query = db.table("products").select("id,banned,source_rating")

    source_values = set(_normalize_list(source) + _normalize_list(sources))
    type_values = set(_normalize_list(type) + _normalize_list(types))
    tag_values = _normalize_list(tags)

    if source_values:
        query = query.in_("source", list(source_values))
    
    if type_values:
        query = query.in_("type", list(type_values))

    if tag_values:
        product_ids_with_tags = get_product_ids_for_tags(db, tag_values, tag_mode)
        if not product_ids_with_tags:
            return {"count": 0}
        query = query.in_("id", list(product_ids_with_tags))
    
    if search:
        query = query.ilike("name", f"%{search}%")
    
    if created_by:
        query = query.eq("created_by", created_by)
    
    if include_banned:
        if not current_user or current_user.get("role") not in {"admin", "moderator"}:
            raise HTTPException(status_code=403, detail="Moderator or admin role required to view banned products")
    
    response = query.execute()
    products = response.data or []
    
    if not include_banned:
        products = [p for p in products if not p.get("banned")]

    # If no rating filter is requested, skip rating lookups to avoid heavy IN queries.
    if min_rating is None:
        return {"count": len(products)}

    ratings_map = build_display_rating_map(db, products)
    products = [p for p in products if rating_meets_threshold(p, ratings_map, min_rating)]
    
    return {"count": len(products)}


@router.get("/exists")
async def product_exists(
    url: str,
    db = Depends(get_db),
):
    """Check if a product exists by its source URL.
    
    Used by scrapers and frontend to avoid duplicate submissions.
    Returns {exists: bool, product: ProductResponse | null}.
    """
    response = db.table("products").select("*").eq("url", url).limit(1).execute()
    if response.data:
        item = response.data[0]
        if item.get("banned"):
            return {"exists": True, "product": _normalize_product(item, db), "banned": True}
        # Normalize fields
        item["tags"] = item.get("tags") or []
        item["stars"] = item.get("source_rating_count") or 0
        if "image" in item:
            item["image_url"] = item.get("image")
        if "url" in item:
            item["source_url"] = item.get("url")
        # Add editor_ids from relationship table
        owners_response = db.table("product_editors").select("user_id").eq("product_id", item["id"]).execute()
        item["editor_ids"] = [owner["user_id"] for owner in owners_response.data] if owners_response.data else []
        attach_rating_fields(db, item)
        return {"exists": True, "product": item}
    return {"exists": False}


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db = Depends(get_db),
):
    """Get a single product by ID"""
    response = db.table("products").select("*").eq("id", product_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Product not found")
    
    result = response.data[0]
    # Attach editor_ids
    owners_response = db.table("product_editors").select("user_id").eq("product_id", product_id).execute()
    result["editor_ids"] = [row["user_id"] for row in owners_response.data] if owners_response.data else []
    # Attach tags via relationship
    pt_rows = get_product_tag_rows(db, [product_id])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    result["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
    # Add top-level stars derived from source_rating_count
    result["stars"] = result.get("source_rating_count") or 0
    # Normalize fields for API clients
    if "image" in result:
        result["image_url"] = result.get("image")
    if "url" in result:
        result["source_url"] = result.get("url")
    attach_rating_fields(db, result)
    
    return result


@router.get("/slug/{slug}", response_model=ProductResponse)
async def get_product_by_slug(
    slug: str,
    db = Depends(get_db),
):
    """Get a single product by slug (human-readable ID)"""
    response = db.table("products").select("*").eq("slug", slug).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Product not found")

    result = response.data[0]
    owners_response = db.table("product_editors").select("user_id").eq("product_id", result["id"]).execute()
    result["editor_ids"] = [row["user_id"] for row in owners_response.data] if owners_response.data else []
    pt_rows = get_product_tag_rows(db, [result["id"]])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    result["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
    result["stars"] = result.get("source_rating_count") or 0
    if "image" in result:
        result["image_url"] = result.get("image")
    if "url" in result:
        result["source_url"] = result.get("url")
    attach_rating_fields(db, result)

    return result


def _normalize_product(product: dict, db) -> dict:
    """Attach derived fields (owners, tags, stars, url/image aliases)."""
    pid = product.get("id")
    owners_response = db.table("product_editors").select("user_id").eq("product_id", pid).execute()
    product["editor_ids"] = [row["user_id"] for row in owners_response.data] if owners_response.data else []

    pt_rows = get_product_tag_rows(db, [pid])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    product["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]

    product["stars"] = product.get("source_rating_count") or 0
    if "image" in product:
        product["image_url"] = product.get("image")
    if "url" in product:
        product["source_url"] = product.get("url")
    attach_rating_fields(db, product)
    return product



@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    product: ProductCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Create a new product (authenticated users only).
    
    Validates product URL against supported sources and auto-assigns source name.
    Supports upsert by URL: if product with same URL exists, updates it instead.
    Automatically adds creator as product editor/owner in product_editors table.
    Security: Requires valid auth token; all users can create products.
    """
    # Get list of supported sources
    sources_response = db.table("supported_sources").select("domain, name").execute()
    supported_sources = sources_response.data or []
    
    # Extract domain from URL and validate against supported sources
    source_url = str(product.source_url) if product.source_url else None
    determined_source = None
    
    if not source_url:
        raise HTTPException(status_code=400, detail="Product URL is required")
    
    domain = extract_domain(source_url)
    if domain:
        determined_source = find_source_for_domain(domain, supported_sources)
    
    # If URL provided but domain not in supported list, reject the submission
    if not determined_source:
        raise HTTPException(
            status_code=400,
            detail=f"URL domain is not supported. Supported domains are: {', '.join([s['domain'] for s in supported_sources])}"
        )
    
    # Map Pydantic model fields to database columns (use attributes to avoid alias issues)
    db_data = {
        "name": product.name,
        "description": product.description,
        "url": source_url,
        "image": str(product.image_url) if product.image_url else None,
        "source": determined_source,  # Auto-assigned, not from user input
        "type": product.type or "Other",
        "external_id": product.external_id,
        "created_by": current_user["id"]
    }

    # Upsert behavior: If URL provided and product exists, update instead of creating.
    # This prevents duplicate products from scrapers while allowing manual updates.
    if db_data.get("url"):
        existing = db.table("products").select("*").eq("url", db_data["url"]).limit(1).execute()
        if existing.data:
            existing_product = existing.data[0]
            if existing_product.get("banned"):
                raise HTTPException(status_code=403, detail="Product is banned and cannot be resubmitted")
            # Build update data, excluding immutable fields like created_by
            update_data = {k: v for k, v in db_data.items() if k in {
                "name", "description", "url", "image", "source", "type", "external_id"
            } and v is not None}

            # Ensure legacy rows get a slug assigned
            if not existing_product.get("slug"):
                update_data["slug"] = generate_id_with_uniqueness_check(product.name, db, "products", column="slug")
            updated = db.table("products").update(update_data).eq("id", existing_product["id"]).execute()
            result = updated.data[0] if updated.data else existing_product
            product_id = result["id"]
            # Normalize fields for API response
            result["image_url"] = result.get("image")
            result["external_id"] = result.get("external_id")
            
            # Add current user as owner if not already one
            existing_owner = db.table("product_editors").select("*").eq("product_id", product_id).eq("user_id", current_user["id"]).execute()
            if not existing_owner.data:
                import uuid
                owner_data = {
                    "id": str(uuid.uuid4()),
                    "product_id": product_id,
                    "user_id": current_user["id"]
                }
                db.table("product_editors").insert(owner_data).execute()
            
            # Add editor_ids to response
            owners_response = db.table("product_editors").select("user_id").eq("product_id", product_id).execute()
            result["editor_ids"] = [owner["user_id"] for owner in owners_response.data] if owners_response.data else []
            
            # Update tag relationships if provided
            if product.tags is not None:
                set_product_tags(db, result["id"], product.tags)
            # Attach tags for response
            pt_rows = get_product_tag_rows(db, [result["id"]])
            tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
            tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
            result["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
            return result

    # Generate human-readable slug for URLs (unique per product)
    slug = generate_id_with_uniqueness_check(product.name, db, "products", column="slug")

    # Add the generated slug to the insert data
    db_insert = {k: v for k, v in db_data.items() if v is not None}
    db_insert["slug"] = slug
    response = db.table("products").insert(db_insert).execute()

    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create product")

    # Map database response back to API response format
    result = response.data[0]
    product_id = result["id"]
    result["image_url"] = result.get("image")
    result["external_id"] = result.get("external_id")
    
    # Add creator as product manager
    import uuid
    owner_data = {
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "user_id": current_user["id"]
    }
    db.table("product_editors").insert(owner_data).execute()
    
    # Add editor_ids to response
    owners_response = db.table("product_editors").select("user_id").eq("product_id", product_id).execute()
    result["editor_ids"] = [owner["user_id"] for owner in owners_response.data] if owners_response.data else []
    
    # Create tag relationships if provided
    if product.tags:
        set_product_tags(db, result["id"], product.tags)
    # Attach tags for response
    pt_rows = get_product_tag_rows(db, [result["id"]])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    result["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]

    return result


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product: ProductUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Update a product (creator/editor or admin only).
    
    Security: Enforces ownership via product_editors table OR admin role.
    Prevents unauthorized users from modifying products they don't manage.
    """
    # Check if product exists and user has permission
    existing = db.table("products").select("*").eq("id", product_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if existing.data[0].get("banned"):
        raise HTTPException(status_code=403, detail="Product is banned and cannot be edited")

    if existing.data[0]["created_by"] != current_user["id"] and not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Not authorized to update this product")
    
    # Map API fields to database columns (use attributes to avoid alias issues)
    product_data = product.model_dump(exclude_unset=True)
    db_data = {}

    if "name" in product_data:
        db_data["name"] = product_data["name"]
    if "description" in product_data:
        db_data["description"] = product_data["description"]
    if "source_url" in product_data and product.source_url is not None:
        db_data["url"] = str(product.source_url)
    if "image_url" in product_data and product.image_url is not None:
        db_data["image"] = str(product.image_url)
    if "source" in product_data:
        db_data["source"] = product_data["source"]
    if "type" in product_data and product.type is not None:
        db_data["type"] = product.type
    if "external_id" in product_data:
        db_data["external_id"] = product_data["external_id"]
    # Apply basic field updates
    
    response = db.table("products").update(db_data).eq("id", product_id).execute()
    
    # Update tag relationships if requested
    if "tags" in product_data:
        set_product_tags(db, product_id, product_data["tags"] or [])

    # Map database response back to API format
    result = response.data[0]
    result["image_url"] = result.get("image")
    result["external_id"] = result.get("external_id")
    # Attach editor_ids
    owners_response = db.table("product_editors").select("user_id").eq("product_id", product_id).execute()
    result["editor_ids"] = [owner["user_id"] for owner in owners_response.data] if owners_response.data else []
    # Attach tags
    pt_rows = get_product_tag_rows(db, [product_id])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    result["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
    
    return result


@router.patch("/{product_id}", response_model=ProductResponse)
async def patch_product(
    product_id: str,
    product: ProductUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Partially update a product (manager or admin only)"""
    # Check if product exists
    existing = db.table("products").select("*").eq("id", product_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check authorization: must be creator, product manager, or admin
    product_row = existing.data[0]
    if product_row.get("banned"):
        raise HTTPException(status_code=403, detail="Product is banned and cannot be edited")
    is_creator = product_row["created_by"] == current_user["id"]
    is_admin = current_user.get("role") == "admin"
    
    # Check if user is a product manager
    is_product_owner = False
    if not (is_creator or is_admin):
        owner_response = db.table("product_editors").select("*").eq("product_id", product_id).eq("user_id", current_user["id"]).execute()
        is_product_owner = bool(owner_response.data)
    
    if not (is_creator or is_admin or is_product_owner):
        raise HTTPException(status_code=403, detail="Only product editors or admins can edit this product")
    
    # Map API fields to database columns
    product_data = product.model_dump(exclude_unset=True)
    db_data = {}

    if "name" in product_data:
        db_data["name"] = product_data["name"]
    if "description" in product_data:
        db_data["description"] = product_data["description"]
    if "source_url" in product_data and product.source_url is not None:
        db_data["url"] = str(product.source_url)
    if "image_url" in product_data and product.image_url is not None:
        db_data["image"] = str(product.image_url)
    if "source" in product_data:
        db_data["source"] = product_data["source"]
    if "type" in product_data and product.type is not None:
        db_data["type"] = product.type
    if "external_id" in product_data:
        db_data["external_id"] = product_data["external_id"]
    
    response = db.table("products").update(db_data).eq("id", product_id).execute()
    
    # Update tag relationships if requested
    if "tags" in product_data:
        set_product_tags(db, product_id, product_data["tags"] or [])

    # Map database response back to API format
    result = response.data[0]
    result["image_url"] = result.get("image")
    result["external_id"] = result.get("external_id")
    # Attach editor_ids
    editors_response = db.table("product_editors").select("user_id").eq("product_id", product_id).execute()
    result["editor_ids"] = [editor["user_id"] for editor in editors_response.data] if editors_response.data else []
    # Attach tags
    pt_rows = get_product_tag_rows(db, [product_id])
    tag_ids = [row["tag_id"] for row in pt_rows] if pt_rows else []
    tags_map = get_tags_map(db, tag_ids) if tag_ids else {}
    result["tags"] = [tags_map[tid] for tid in tag_ids if tid in tags_map]
    
    return result


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Delete a product (admin only)"""
    if not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    response = db.table("products").delete().eq("id", product_id).execute()
    
    if response.count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return None


def _ensure_moderator_or_admin(current_user: dict):
    if not current_user or current_user.get("role") not in {"admin", "moderator"}:
        raise HTTPException(status_code=403, detail="Moderator or admin access required")


@router.post("/{product_id}/ban", response_model=ProductResponse)
async def ban_product(
    product_id: str,
    payload: dict = None,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Ban a product from scraper updates (moderator/admin)."""
    _ensure_moderator_or_admin(current_user)

    # Ensure product exists
    product_response = db.table("products").select("*").eq("id", product_id).limit(1).execute()
    if not product_response.data:
        raise HTTPException(status_code=404, detail="Product not found")

    reason = None
    if payload:
        reason = payload.get("reason")

    update_data = {
        "banned": True,
        "banned_reason": reason,
        "banned_by": current_user.get("id"),
        "banned_at": datetime.now(UTC)
    }

    updated = db.table("products").update(update_data).eq("id", product_id).execute()
    if not updated.data:
        raise HTTPException(status_code=404, detail="Product not found")

    product = updated.data[0]
    return _normalize_product(product, db)


@router.post("/{product_id}/unban", response_model=ProductResponse)
async def unban_product(
    product_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Remove ban from a product (moderator/admin)."""
    _ensure_moderator_or_admin(current_user)

    updated = db.table("products").update({
        "banned": False,
        "banned_reason": None,
        "banned_by": None,
        "banned_at": None
    }).eq("id", product_id).execute()

    if not updated.data:
        raise HTTPException(status_code=404, detail="Product not found")

    product = updated.data[0]
    return _normalize_product(product, db)


@router.get("/{product_id}/owners")
async def get_product_editors(
    product_id: str,
    db = Depends(get_db),
):
    """Get all editors of a product"""
    # First check if product exists
    product_response = db.table("products").select("id").eq("id", product_id).execute()
    if not product_response.data:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get all editor relationships
    editors_response = db.table("product_editors").select("user_id").eq("product_id", product_id).execute()
    
    if not editors_response.data:
        return []
    
    # Get user details for each editor
    user_ids = [editor["user_id"] for editor in editors_response.data]
    users_response = db.table("users").select("*").in_("id", user_ids).execute()
    
    return users_response.data or []


# ------------------------------
# Tag helpers
# ------------------------------

def get_product_tag_rows(db, product_ids: list[str]):
    """Fetch product_tags rows for given product IDs"""
    return db.table("product_tags").select("*").in_("product_id", product_ids).execute().data


def get_tags_map(db, tag_ids: list[str]):
    """Fetch tags by IDs and return map id -> name"""
    if not tag_ids:
        return {}
    rows = db.table("tags").select("*").in_("id", tag_ids).execute().data
    return {row["id"]: row["name"] for row in rows}


def get_or_create_tag_ids(db, tag_names: list[str]) -> dict[str, str]:
    """Return map name -> id, creating tags as needed."""
    if not tag_names:
        return {}
    # Existing tags
    existing = db.table("tags").select("*").in_("name", tag_names).execute().data
    by_name = {row["name"]: row["id"] for row in existing}
    # Create missing
    missing = [name for name in tag_names if name not in by_name]
    if missing:
        created = db.table("tags").insert([{ "name": name } for name in missing]).execute().data
        for row in created:
            by_name[row["name"]] = row["id"]
    return by_name


def set_product_tags(db, product_id: str, tag_names: list[str]):
    """Replace product's tag relationships with given names."""
    # Clear existing relationships
    db.table("product_tags").delete().eq("product_id", product_id).execute()
    if not tag_names:
        return
    # Get tag IDs
    name_to_id = get_or_create_tag_ids(db, tag_names)
    # Create relationships
    payload = [{"product_id": product_id, "tag_id": tid} for tid in name_to_id.values()]
    db.table("product_tags").insert(payload).execute()

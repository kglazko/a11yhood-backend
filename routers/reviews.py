from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from supabase import Client

from models.reviews import ReviewCreate, ReviewUpdate, ReviewResponse
from services.database import get_db
from services.auth import get_current_user

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewResponse])
async def get_reviews(
    product_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db),
):
    """Get reviews with optional filters"""
    query = db.table("reviews").select("*")
    
    if product_id:
        query = query.eq("product_id", product_id)
    
    if user_id:
        query = query.eq("user_id", user_id)
    
    query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
    
    response = query.execute()
    return response.data


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    db = Depends(get_db),
):
    """Get a single review by ID"""
    response = db.table("reviews").select("*").eq("id", review_id).execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return response.data[0]


@router.post("", response_model=ReviewResponse, status_code=201)
async def create_review(
    review: ReviewCreate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Create a new review (authenticated users only)"""
    review_data = review.model_dump()
    review_data["user_id"] = current_user["id"]
    
    # Fetch user's username from users table
    user_response = db.table("users").select("username").eq("id", current_user["id"]).execute()
    if user_response.data:
        review_data["username"] = user_response.data[0]["username"]
    
    response = db.table("reviews").insert(review_data).execute()
    
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to create review")
    
    return response.data[0]


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str,
    review: ReviewUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Update a review (owner only)"""
    existing = db.table("reviews").select("*").eq("id", review_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Review not found")
    
    if existing.data[0]["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this review")
    
    update_data = review.model_dump(exclude_unset=True)
    response = db.table("reviews").update(update_data).eq("id", review_id).execute()
    
    return response.data[0]


@router.delete("/{review_id}", status_code=204)
async def delete_review(
    review_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
    """Delete a review (owner or admin only)"""
    existing = db.table("reviews").select("*").eq("id", review_id).execute()
    
    if not existing.data:
        raise HTTPException(status_code=404, detail="Review not found")
    
    if existing.data[0]["user_id"] != current_user["id"] and not current_user.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this review")
    
    db.table("reviews").delete().eq("id", review_id).execute()
    return None

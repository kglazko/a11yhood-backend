"""
User activity models for tracking user actions.
"""
from pydantic import BaseModel
from typing import Optional


class UserActivityCreate(BaseModel):
    """Request model for creating user activity"""
    user_id: str
    type: str  # 'product_submit' | 'rating' | 'discussion' | 'tag'
    product_id: Optional[str] = None
    timestamp: int  # milliseconds since epoch
    metadata: Optional[dict] = None


class UserActivityResponse(BaseModel):
    """Response model for user activity"""
    id: str
    user_id: str
    type: str
    product_id: Optional[str] = None
    timestamp: int
    created_at: Optional[str] = None
    metadata: Optional[dict] = None

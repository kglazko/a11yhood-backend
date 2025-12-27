from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReviewBase(BaseModel):
    product_id: str
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)


class ReviewResponse(ReviewBase):
    id: str
    user_id: str
    username: str  # User's username from users table
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

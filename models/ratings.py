from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class RatingBase(BaseModel):
    product_id: str
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    owned: bool = False


class RatingCreate(RatingBase):
    pass


class RatingUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    owned: Optional[bool] = None


class RatingResponse(RatingBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

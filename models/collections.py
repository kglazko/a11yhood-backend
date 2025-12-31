from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class CollectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_public: bool = Field(default=True)


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_public: Optional[bool] = None


class ProductIdsRequest(BaseModel):
    product_ids: List[str] = Field(default_factory=list)


class CollectionFromSearchCreate(CollectionBase):
    """Create a collection from search results."""
    source: Optional[List[str]] = Field(None, description="Source filter for search")
    sources: Optional[List[str]] = Field(None, description="Source filter for search")
    type: Optional[List[str]] = Field(None, description="Type filter for search")
    types: Optional[List[str]] = Field(None, description="Type filter for search")
    tags: Optional[List[str]] = Field(None, description="Tag filter for search")
    tags_mode: str = Field(default="or", pattern=r"^(?i)(or|and)$", description="Tag filter mode: or or and")
    search: Optional[str] = Field(None, description="Text search on product name")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum rating filter")
    created_by: Optional[str] = Field(None, description="Filter by creator user ID")


class CollectionResponse(CollectionBase):
    id: str
    user_id: str
    user_name: str
    product_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

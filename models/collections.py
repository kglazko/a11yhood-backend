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


class CollectionResponse(CollectionBase):
    id: str
    user_id: str
    user_name: str
    product_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

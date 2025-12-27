from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional
from datetime import datetime
from models.product_urls import ProductUrlResponse


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source: Optional[str] = None  # Source platform (user-submitted, scraped-ravelry, etc.)
    source_url: Optional[HttpUrl] = None  # URL to the source product
    type: Optional[str] = None  # Product type/category (e.g., Knitting, 3D Printed, Software)
    image_url: Optional[HttpUrl] = None
    external_id: Optional[str] = None  # ID from external source
    tags: Optional[list[str]] = Field(default_factory=list)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[HttpUrl] = None
    type: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    external_id: Optional[str] = None
    tags: Optional[list[str]] = None


class ProductResponse(ProductBase):
    id: str
    slug: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    banned: bool | None = None
    banned_reason: Optional[str] = None
    banned_by: Optional[str] = None
    banned_at: Optional[datetime] = None
    average_rating: Optional[float] = None
    rating_count: int = 0
    source_rating: Optional[float] = None
    source_rating_count: Optional[int] = None
    stars: Optional[int] = None
    urls: list[ProductUrlResponse] = Field(default_factory=list)
    editor_ids: list[str] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)

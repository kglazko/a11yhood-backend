from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BlogPostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=1)
    excerpt: Optional[str] = Field(None, max_length=1000)
    header_image: Optional[str] = None
    header_image_alt: Optional[str] = Field(None, max_length=300)
    tags: List[str] = Field(default_factory=list)
    featured: bool = False
    published: bool = False
    publish_date: Optional[int] = None
    published_at: Optional[int] = None
    author_ids: Optional[List[str]] = None
    author_names: Optional[List[str]] = None


class BlogPostCreate(BlogPostBase):
    author_id: str = Field(..., min_length=1)
    author_name: str = Field(..., min_length=1)


class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    header_image: Optional[str] = None
    header_image_alt: Optional[str] = None
    tags: Optional[List[str]] = None
    featured: Optional[bool] = None
    published: Optional[bool] = None
    publish_date: Optional[int] = None
    published_at: Optional[int] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    author_ids: Optional[List[str]] = None
    author_names: Optional[List[str]] = None


class BlogPostResponse(BlogPostBase):
    id: str
    author_id: str
    author_name: str
    created_at: int
    updated_at: int

    model_config = ConfigDict(from_attributes=True)

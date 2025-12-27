from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class DiscussionBase(BaseModel):
    product_id: str
    content: str = Field(..., min_length=1)
    parent_id: Optional[str] = None


class DiscussionCreate(DiscussionBase):
    pass


class DiscussionUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)


class DiscussionBlockRequest(BaseModel):
    reason: Optional[str] = None


class DiscussionResponse(DiscussionBase):
    id: str
    user_id: str
    username: str
    created_at: datetime
    updated_at: datetime
    blocked: bool = False
    blocked_by: Optional[str] = None
    blocked_reason: Optional[str] = None
    blocked_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


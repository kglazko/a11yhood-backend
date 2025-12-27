from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class SupportedSourceBase(BaseModel):
    domain: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)


class SupportedSourceCreate(SupportedSourceBase):
    pass


class SupportedSourceUpdate(BaseModel):
    domain: Optional[str] = Field(None, min_length=1, max_length=255)
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class SupportedSourceResponse(SupportedSourceBase):
    id: str
    created_at: datetime
    updated_at: datetime

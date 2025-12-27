from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional
from datetime import datetime


class ProductUrlBase(BaseModel):
    url: HttpUrl
    description: Optional[str] = None


class ProductUrlCreate(ProductUrlBase):
    pass


class ProductUrlUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    description: Optional[str] = None


class ProductUrlResponse(ProductUrlBase):
    id: str
    product_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

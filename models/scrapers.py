from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional, List
from datetime import datetime


class ScrapingLogBase(BaseModel):
    source: str
    products_found: int
    products_added: int
    products_updated: int
    duration_seconds: float
    status: str  # 'success', 'error', 'halted'
    error_message: Optional[str] = None


class ScrapingLogCreate(ScrapingLogBase):
    pass


class ScrapingLogResponse(ScrapingLogBase):
    id: str
    user_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OAuthConfigBase(BaseModel):
    platform: str  # 'ravelry', 'thingiverse', 'github'
    client_id: str
    client_secret: str
    redirect_uri: str


class OAuthConfigCreate(OAuthConfigBase):
    pass


class OAuthConfigUpdate(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None


class OAuthConfigResponse(BaseModel):
    id: str
    platform: str
    client_id: str
    redirect_uri: str
    created_at: datetime
    updated_at: datetime
    # client_secret is intentionally excluded for security
    
    model_config = ConfigDict(from_attributes=True)


from enum import Enum


class ScraperSource(str, Enum):
    """Valid scraper sources"""
    thingiverse = "thingiverse"
    ravelry = "ravelry"
    github = "github"


class ScraperTriggerRequest(BaseModel):
    source: ScraperSource = Field(..., description="Platform to scrape: 'thingiverse', 'ravelry', 'github'")
    test_mode: bool = Field(False, description="If true, only scrape limited items for testing")
    test_limit: int = Field(5, description="Number of items to scrape in test mode", ge=1, le=50)

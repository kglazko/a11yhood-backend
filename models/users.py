"""User account Pydantic models for request/response validation.

Defines schemas for user CRUD operations with role management.
Email validation enforced via EmailStr for security.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    products_owned: Optional[list[str]] = None
    role: Optional[str] = None


class UserResponse(UserBase):
    id: str
    products_owned: list[str] = []
    role: str = "user"
    created_at: datetime
    updated_at: datetime
    username_display: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile with statistics"""
    ratings_count: Optional[int] = None
    discussions_count: Optional[int] = None

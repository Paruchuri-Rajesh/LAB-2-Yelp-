from __future__ import annotations
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date, datetime


class ReviewCreate(BaseModel):
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    visited_at: Optional[date] = None

    @field_validator("rating")
    @classmethod
    def valid_rating(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None
    visited_at: Optional[date] = None

    @field_validator("rating")
    @classmethod
    def valid_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


class ReviewAuthor(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    profile_picture_path: Optional[str] = None


class ReviewRead(BaseModel):
    id: str
    restaurant_id: str
    restaurant_name: Optional[str] = None
    user_id: Optional[str] = None
    rating: Optional[int] = None
    title: Optional[str] = None
    body: Optional[str] = None
    visited_at: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source: str = "local"
    author_name: Optional[str] = None
    author_image_url: Optional[str] = None
    source_url: Optional[str] = None
    user: Optional[ReviewAuthor] = None


class ReviewsResponse(BaseModel):
    items: list[ReviewRead]
    total: int
    page: int
    page_size: int
    pages: int


class ReviewAccepted(BaseModel):
    status: str = "accepted"
    event_id: Optional[str] = None
    message: str

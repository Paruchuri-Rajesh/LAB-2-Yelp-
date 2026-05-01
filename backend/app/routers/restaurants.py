import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile, status

from app.dependencies import get_current_user, get_optional_current_user
from app.kafka_utils import Topics, publish_event
from app.schemas.restaurant import (
    RestaurantDetail,
    RestaurantSearchResponse,
    RestaurantListItem,
    RestaurantPlaceItem,
)
from app.schemas.review import ReviewAccepted, ReviewCreate
from app.services import file_service
from app.services.restaurant_service import (
    search_restaurants,
    get_restaurant_by_id,
    search_places,
    record_restaurant_view,
    create_restaurant,
)
from app.services.review_service import (
    assert_user_can_review,
    build_create_payload,
)
from app.services.user_service import is_favorited
from app.database import get_db

router = APIRouter()


@router.get("/places", response_model=list[RestaurantPlaceItem])
async def places(q: Optional[str] = None, limit: int = 8):
    return await search_places(q=q, limit=limit)


@router.get("", response_model=RestaurantSearchResponse)
async def search(
    q: Optional[str] = None,
    cuisine: Optional[str] = None,
    location: Optional[str] = None,
    city: Optional[str] = None,
    price_range: Optional[str] = None,
    min_rating: Optional[float] = None,
    sort_by: str = "recommended",
    page: int = 1,
    page_size: int = 20,
    open_now: bool | None = None,
    has_reservations: bool | None = None,
    offers_delivery: bool | None = None,
    offers_takeout: bool | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_miles: float | None = None,
    current_user=Depends(get_optional_current_user),
):
    items, total = await search_restaurants(
        q=q, cuisine=cuisine, location=location, city=city, price_range=price_range,
        min_rating=min_rating, sort_by=sort_by, page=page, page_size=page_size,
        open_now=open_now, has_reservations=has_reservations,
        offers_delivery=offers_delivery, offers_takeout=offers_takeout,
        latitude=latitude, longitude=longitude, radius_miles=radius_miles,
    )

    fav_ids: set[str] = set()
    if current_user and items:
        db = get_db()
        cursor = db.favorites.find(
            {"user_id": current_user["id"], "restaurant_id": {"$in": [r["id"] for r in items]}}
        )
        fav_ids = {f["restaurant_id"] async for f in cursor}

    list_items = [
        RestaurantListItem(
            id=r["id"],
            name=r.get("name") or "",
            slug=r.get("slug"),
            cuisine_type=r.get("cuisine_type"),
            city=r.get("city"),
            state=r.get("state"),
            address=r.get("address"),
            zip_code=r.get("zip_code"),
            price_range=r.get("price_range"),
            avg_rating=float(r.get("avg_rating") or 0),
            review_count=int(r.get("review_count") or 0),
            primary_photo=r.get("primary_photo"),
            latitude=r.get("latitude"),
            longitude=r.get("longitude"),
            source=r.get("source") or "local",
            is_favorited=r["id"] in fav_ids,
        )
        for r in items
    ]
    return RestaurantSearchResponse(
        items=list_items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/{restaurant_id}", response_model=RestaurantDetail)
async def get_restaurant(restaurant_id: str, current_user=Depends(get_optional_current_user)):
    restaurant = await get_restaurant_by_id(restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.")
    await record_restaurant_view(restaurant_id, viewer_user_id=current_user["id"] if current_user else None)
    restaurant["is_favorited"] = await is_favorited(current_user["id"] if current_user else None, restaurant_id)
    return restaurant


@router.post("/suggest", response_model=RestaurantDetail, status_code=201)
async def suggest_restaurant(
    name: str = Form(...),
    address: str | None = Form(None),
    city: str | None = Form(None),
    state: str | None = Form(None),
    zip_code: str | None = Form(None),
    phone: str | None = Form(None),
    website: str | None = Form(None),
    cuisine_type: str | None = Form(None),
    price_range: str | None = Form(None),
    description: str | None = Form(None),
    photos: list[UploadFile] | None = File(None),
    rating: int | None = Form(None),
    title: str | None = Form(None),
    body: str | None = Form(None),
    visited_at: date | None = Form(None),
    current_user=Depends(get_current_user),
):
    photo_payload = []
    if photos:
        for idx, f in enumerate(photos):
            path = await file_service.save_upload(f, "restaurant_photos")
            photo_payload.append({"file_path": path, "is_primary": idx == 0})

    rest = await create_restaurant(
        {
            "name": name,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "phone": phone,
            "website": website,
            "cuisine_type": cuisine_type,
            "price_range": price_range,
            "description": description,
            "photos": photo_payload,
        },
        source="suggested",
    )
    await publish_event(Topics.RESTAURANT_CREATED, {
        "restaurant_id": rest["id"],
        "source": "suggested",
        "suggested_by": current_user["id"],
    }, key=rest["id"])

    if rating is not None:
        await assert_user_can_review(rest["id"], current_user["id"])
        payload = build_create_payload(
            rest["id"], current_user["id"], current_user.get("name"),
            ReviewCreate(rating=rating, title=title, body=body, visited_at=visited_at),
        )
        await publish_event(Topics.REVIEW_CREATED, payload, key=rest["id"])

    return rest


@router.post("/{restaurant_id}/reviews/accept", response_model=ReviewAccepted, status_code=status.HTTP_202_ACCEPTED)
async def review_accepted_stub():
    """Kept so the OpenAPI schema documents the asynchronous review path."""
    return ReviewAccepted(message="Review accepted for processing")

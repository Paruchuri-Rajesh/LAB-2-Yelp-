from datetime import time
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_owner
from app.kafka_utils import Topics, publish_event
from app.schemas.owner import OwnerDashboardSummary, OwnerRestaurantDashboard
from app.schemas.restaurant import RestaurantDetail, RestaurantUpdate
from app.services import file_service
from app.services.restaurant_service import (
    claim_restaurant,
    create_restaurant,
    get_owner_dashboard_summary,
    get_owner_restaurant_dashboard,
    get_owner_restaurants,
    get_restaurant_by_id,
    update_owned_restaurant,
)


class HoursIn(BaseModel):
    day_of_week: str
    open_time: time | None = None
    close_time: time | None = None
    is_closed: bool = False


router = APIRouter()


async def _ensure_ownership(restaurant_id: str, owner_id: str) -> None:
    if not await get_db().ownerships.find_one({"restaurant_id": restaurant_id, "owner_id": owner_id}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner does not own this restaurant")


@router.post("/restaurants", response_model=RestaurantDetail, status_code=status.HTTP_201_CREATED)
async def create_my_restaurant(
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
    current_owner=Depends(get_current_owner),
):
    photo_payload = []
    if photos:
        for idx, f in enumerate(photos):
            path = await file_service.save_upload(f, "restaurant_photos")
            photo_payload.append({"file_path": path, "is_primary": idx == 0})

    rest = await create_restaurant({
        "name": name, "address": address, "city": city, "state": state, "zip_code": zip_code,
        "phone": phone, "website": website, "cuisine_type": cuisine_type, "price_range": price_range,
        "description": description, "photos": photo_payload,
    }, source="local")

    await claim_restaurant(rest["id"], current_owner["id"])
    await publish_event(Topics.RESTAURANT_CREATED, {
        "restaurant_id": rest["id"], "owner_id": current_owner["id"], "source": "local",
    }, key=rest["id"])
    await publish_event(Topics.RESTAURANT_CLAIMED, {
        "restaurant_id": rest["id"], "owner_id": current_owner["id"],
    }, key=rest["id"])
    return rest


@router.post("/restaurants/{restaurant_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_restaurant_photos(
    restaurant_id: str,
    photos: list[UploadFile] | None = File(None),
    current_owner=Depends(get_current_owner),
):
    await _ensure_ownership(restaurant_id, current_owner["id"])
    added = 0
    if photos:
        for f in photos:
            path = await file_service.save_upload(f, "restaurant_photos")
            await get_db().restaurants.update_one(
                {"_id": ObjectId(restaurant_id)},
                {"$push": {"photos": {"file_path": path, "is_primary": False, "caption": None}}},
            )
            added += 1
    return {"added": added}


@router.delete("/restaurants/{restaurant_id}/photos/{photo_index}", status_code=200)
async def delete_restaurant_photo(
    restaurant_id: str,
    photo_index: int,
    current_owner=Depends(get_current_owner),
):
    """Remove a photo by array index. Photos are embedded in the restaurant
    document, so we pull the one at ``photos[photo_index]`` and trust the
    client to pass the index it read from the detail response."""
    await _ensure_ownership(restaurant_id, current_owner["id"])
    doc = await get_db().restaurants.find_one({"_id": ObjectId(restaurant_id)}, {"photos": 1})
    photos = (doc or {}).get("photos") or []
    if photo_index < 0 or photo_index >= len(photos):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    photo = photos[photo_index]
    if photo.get("file_path"):
        file_service.delete_file(photo["file_path"])
    del photos[photo_index]
    await get_db().restaurants.update_one({"_id": ObjectId(restaurant_id)}, {"$set": {"photos": photos}})
    return {"deleted": photo_index}


@router.put("/restaurants/{restaurant_id}/hours", status_code=200)
async def update_restaurant_hours(
    restaurant_id: str,
    hours: List[HoursIn],
    current_owner=Depends(get_current_owner),
):
    await _ensure_ownership(restaurant_id, current_owner["id"])
    hours_docs = [
        {
            "day_of_week": h.day_of_week,
            "open_time": h.open_time.isoformat() if h.open_time else None,
            "close_time": h.close_time.isoformat() if h.close_time else None,
            "is_closed": h.is_closed,
        }
        for h in hours
    ]
    await get_db().restaurants.update_one({"_id": ObjectId(restaurant_id)}, {"$set": {"hours": hours_docs}})
    return {"updated": len(hours_docs)}


@router.post("/restaurants/{restaurant_id}/claim", status_code=status.HTTP_201_CREATED)
async def claim_my_restaurant(restaurant_id: str, current_owner=Depends(get_current_owner)):
    claim = await claim_restaurant(restaurant_id, current_owner["id"])
    await publish_event(Topics.RESTAURANT_CLAIMED, {
        "restaurant_id": restaurant_id, "owner_id": current_owner["id"],
    }, key=restaurant_id)
    return claim


@router.get("/restaurants")
async def list_owned_restaurants(current_owner=Depends(get_current_owner)):
    return await get_owner_restaurants(current_owner["id"])


@router.get("/dashboard", response_model=OwnerDashboardSummary)
async def owner_dashboard(current_owner=Depends(get_current_owner)):
    return await get_owner_dashboard_summary(current_owner["id"])


@router.get("/restaurants/{restaurant_id}/dashboard", response_model=OwnerRestaurantDashboard)
async def owner_restaurant_dashboard(restaurant_id: str, current_owner=Depends(get_current_owner)):
    return await get_owner_restaurant_dashboard(current_owner["id"], restaurant_id)


@router.put("/restaurants/{restaurant_id}", response_model=RestaurantDetail)
async def update_my_restaurant(
    restaurant_id: str,
    data: RestaurantUpdate,
    current_owner=Depends(get_current_owner),
):
    update_data = data.model_dump(exclude_unset=True)
    updated = await update_owned_restaurant(current_owner["id"], restaurant_id, update_data)
    await publish_event(Topics.RESTAURANT_UPDATED, {
        "restaurant_id": restaurant_id, "changes": update_data, "owner_id": current_owner["id"],
    }, key=restaurant_id)
    return updated

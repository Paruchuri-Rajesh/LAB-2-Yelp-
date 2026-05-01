"""Restaurant-related Mongo operations."""
from datetime import datetime
from math import cos, radians
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.database import get_db
from app.models import doc_out, to_object_id


def _photos_primary(photos: list[dict] | None) -> str | None:
    if not photos:
        return None
    primary = next((p for p in photos if p.get("is_primary")), None)
    return (primary or photos[0]).get("file_path")


def _shape_restaurant(doc: dict) -> dict:
    out = doc_out(doc) or {}
    photos = out.get("photos") or []
    out["primary_photo"] = _photos_primary(photos) or out.get("image_url")
    out["is_active"] = not bool(out.get("is_closed"))
    return out


def _build_search_filter(
    q: str | None,
    cuisine: str | None,
    location: str | None,
    city: str | None,
    price_range: str | None,
    min_rating: float | None,
    offers_delivery: bool | None,
    offers_takeout: bool | None,
    has_reservations: bool | None,
    latitude: float | None,
    longitude: float | None,
    radius_miles: float | None,
) -> dict:
    mongo_filter: dict[str, Any] = {"is_closed": {"$ne": True}}
    and_clauses: list[dict] = []

    if q:
        regex = {"$regex": q, "$options": "i"}
        and_clauses.append({"$or": [
            {"name": regex}, {"cuisine_type": regex}, {"description": regex},
            {"address": regex}, {"city": regex},
        ]})
    if cuisine:
        and_clauses.append({"cuisine_type": {"$regex": cuisine, "$options": "i"}})
    if location:
        regex = {"$regex": location, "$options": "i"}
        and_clauses.append({"$or": [
            {"city": regex}, {"state": regex}, {"zip_code": regex},
            {"address": regex}, {"source": "suggested"},
        ]})
    if city:
        and_clauses.append({"city": {"$regex": city, "$options": "i"}})
    if price_range:
        mongo_filter["price_range"] = price_range
    if min_rating is not None:
        mongo_filter["avg_rating"] = {"$gte": float(min_rating)}
    if offers_delivery:
        mongo_filter["transactions"] = {"$regex": "delivery", "$options": "i"}
    if offers_takeout:
        and_clauses.append({"transactions": {"$regex": "takeout|pickup", "$options": "i"}})
    if has_reservations:
        and_clauses.append({"transactions": {"$regex": "restaurant_reservation", "$options": "i"}})

    if latitude is not None and longitude is not None and radius_miles:
        try:
            lat_delta = float(radius_miles) / 69.0
            lon_divisor = max(abs(cos(radians(float(latitude)))), 0.1)
            lon_delta = float(radius_miles) / (69.0 * lon_divisor)
            mongo_filter["latitude"] = {"$gte": latitude - lat_delta, "$lte": latitude + lat_delta, "$ne": None}
            mongo_filter["longitude"] = {"$gte": longitude - lon_delta, "$lte": longitude + lon_delta, "$ne": None}
        except Exception:
            pass

    if and_clauses:
        mongo_filter["$and"] = and_clauses
    return mongo_filter


_SORT_MAP = {
    "recommended": [("avg_rating", -1), ("review_count", -1), ("name", 1)],
    "rating": [("avg_rating", -1), ("review_count", -1)],
    "review_count": [("review_count", -1), ("avg_rating", -1)],
    "name": [("name", 1)],
    "price": [("price_range", 1), ("avg_rating", -1)],
    "newest": [("created_at", -1)],
}


async def search_restaurants(
    q: str | None = None,
    cuisine: str | None = None,
    location: str | None = None,
    city: str | None = None,
    price_range: str | None = None,
    min_rating: float | None = None,
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
) -> tuple[list[dict], int]:
    db = get_db()
    mongo_filter = _build_search_filter(
        q, cuisine, location, city, price_range, min_rating,
        offers_delivery, offers_takeout, has_reservations,
        latitude, longitude, radius_miles,
    )
    total = await db.restaurants.count_documents(mongo_filter)
    cursor = (
        db.restaurants.find(mongo_filter)
        .sort(_SORT_MAP.get(sort_by, _SORT_MAP["recommended"]))
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_shape_restaurant(doc) async for doc in cursor]
    return items, total


async def search_places(q: str | None = None, limit: int = 8) -> list[dict]:
    db = get_db()
    match: dict[str, Any] = {"is_closed": {"$ne": True}, "city": {"$ne": None}}
    if q:
        regex = {"$regex": q, "$options": "i"}
        match["$or"] = [{"city": regex}, {"state": regex}, {"zip_code": regex}]
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"city": "$city", "state": "$state", "zip_code": "$zip_code"}}},
        {"$limit": limit},
    ]
    results = []
    async for row in db.restaurants.aggregate(pipeline):
        key = row["_id"]
        label = ", ".join(p for p in [key.get("city"), key.get("state"), key.get("zip_code")] if p)
        results.append({"label": label, **{k: key.get(k) for k in ("city", "state", "zip_code")}})
    return results


async def get_restaurant_by_id(restaurant_id: str) -> dict | None:
    oid = to_object_id(restaurant_id)
    if not oid:
        return None
    doc = await get_db().restaurants.find_one({"_id": oid, "is_closed": {"$ne": True}})
    return _shape_restaurant(doc) if doc else None


async def record_restaurant_view(restaurant_id: str, viewer_user_id: str | None = None) -> None:
    await get_db().restaurant_views.insert_one({
        "restaurant_id": restaurant_id,
        "viewer_user_id": viewer_user_id,
        "viewed_at": datetime.utcnow(),
    })


async def recalculate_restaurant_ratings(restaurant_id: str) -> None:
    db = get_db()
    pipeline = [
        {"$match": {"restaurant_id": restaurant_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}, "cnt": {"$sum": 1}}},
    ]
    agg = await db.reviews.aggregate(pipeline).to_list(length=1)
    avg = round(float(agg[0]["avg"]), 2) if agg and agg[0]["avg"] is not None else 0.0
    cnt = int(agg[0]["cnt"]) if agg else 0
    oid = to_object_id(restaurant_id)
    if oid:
        await db.restaurants.update_one({"_id": oid}, {"$set": {"avg_rating": avg, "review_count": cnt}})


async def claim_restaurant(restaurant_id: str, owner_id: str) -> dict:
    db = get_db()
    r_oid = to_object_id(restaurant_id)
    if not r_oid or not await db.restaurants.find_one({"_id": r_oid}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found.")
    existing = await db.ownerships.find_one({"restaurant_id": restaurant_id, "owner_id": owner_id})
    if existing:
        return doc_out(existing)
    now = datetime.utcnow()
    doc = {
        "restaurant_id": restaurant_id,
        "owner_id": owner_id,
        "status": "claimed",
        "created_at": now,
        "updated_at": now,
    }
    result = await db.ownerships.insert_one(doc)
    saved = await db.ownerships.find_one({"_id": result.inserted_id})
    return doc_out(saved)


async def get_owner_restaurants(owner_id: str) -> list[dict]:
    db = get_db()
    owned = db.ownerships.find({"owner_id": owner_id})
    ids = [to_object_id(o["restaurant_id"]) async for o in owned]
    ids = [i for i in ids if i is not None]
    if not ids:
        return []
    cursor = db.restaurants.find({"_id": {"$in": ids}}).sort("name", 1)
    return [_shape_restaurant(r) async for r in cursor]


async def ensure_owner_has_restaurant(owner_id: str, restaurant_id: str) -> dict:
    db = get_db()
    ownership = await db.ownerships.find_one({"owner_id": owner_id, "restaurant_id": restaurant_id})
    if not ownership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owned restaurant not found.")
    oid = to_object_id(restaurant_id)
    doc = await db.restaurants.find_one({"_id": oid}) if oid else None
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owned restaurant not found.")
    return _shape_restaurant(doc)


async def create_restaurant(data: dict, source: str = "local") -> dict:
    db = get_db()
    now = datetime.utcnow()
    doc = {
        "name": data.get("name"),
        "slug": data.get("slug"),
        "cuisine_type": data.get("cuisine_type"),
        "description": data.get("description"),
        "address": data.get("address"),
        "city": data.get("city"),
        "state": data.get("state"),
        "zip_code": data.get("zip_code"),
        "country": data.get("country"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "phone": data.get("phone"),
        "website": data.get("website"),
        "image_url": data.get("image_url"),
        "price_range": data.get("price_range"),
        "avg_rating": 0.0,
        "review_count": 0,
        "is_closed": False,
        "transactions": data.get("transactions"),
        "hours_raw": data.get("hours_raw"),
        "amenities": data.get("amenities"),
        "keywords": data.get("keywords"),
        "source": source,
        "hours": data.get("hours") or [],
        "photos": data.get("photos") or [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.restaurants.insert_one(doc)
    saved = await db.restaurants.find_one({"_id": result.inserted_id})
    return _shape_restaurant(saved)


async def update_owned_restaurant(owner_id: str, restaurant_id: str, data: dict) -> dict:
    await ensure_owner_has_restaurant(owner_id, restaurant_id)
    data["updated_at"] = datetime.utcnow()
    await get_db().restaurants.update_one({"_id": ObjectId(restaurant_id)}, {"$set": data})
    return await get_restaurant_by_id(restaurant_id)


async def get_owner_dashboard_summary(owner_id: str) -> dict:
    db = get_db()
    restaurants = await get_owner_restaurants(owner_id)
    restaurant_ids = [r["id"] for r in restaurants]
    if not restaurant_ids:
        return {"total_restaurants": 0, "total_views": 0, "total_reviews": 0, "avg_rating": 0.0, "recent_reviews": [], "restaurants": []}

    total_views = await db.restaurant_views.count_documents({"restaurant_id": {"$in": restaurant_ids}})
    total_reviews = sum(int(r.get("review_count") or 0) for r in restaurants)
    avg_rating = round(sum(float(r.get("avg_rating") or 0) for r in restaurants) / max(len(restaurants), 1), 2)
    recent_cursor = (
        db.reviews.find({"restaurant_id": {"$in": restaurant_ids}})
        .sort("created_at", -1)
        .limit(5)
    )
    recent_reviews = [doc_out(r) async for r in recent_cursor]
    return {
        "total_restaurants": len(restaurants),
        "total_views": total_views,
        "total_reviews": total_reviews,
        "avg_rating": avg_rating,
        "recent_reviews": recent_reviews,
        "restaurants": restaurants,
    }


async def get_owner_restaurant_dashboard(owner_id: str, restaurant_id: str) -> dict:
    db = get_db()
    restaurant = await ensure_owner_has_restaurant(owner_id, restaurant_id)
    reviews_cursor = db.reviews.find({"restaurant_id": restaurant_id}).sort("created_at", -1)
    reviews = [doc_out(r) async for r in reviews_cursor]
    total_views = await db.restaurant_views.count_documents({"restaurant_id": restaurant_id})
    breakdown = {str(i): 0 for i in range(1, 6)}
    for rv in reviews:
        r = rv.get("rating")
        if r:
            breakdown[str(int(r))] = breakdown.get(str(int(r)), 0) + 1
    return {
        "restaurant": restaurant,
        "total_views": total_views,
        "total_reviews": len(reviews),
        "avg_rating": round(float(restaurant.get("avg_rating") or 0), 2),
        "recent_reviews": reviews[:8],
        "rating_breakdown": {str(i): breakdown.get(str(i), 0) for i in range(5, 0, -1)},
    }
